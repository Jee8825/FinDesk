"""Integration: commit guardrails, tenant isolation, audit-chain tamper proof.

These run against a real Postgres (testcontainers) with the full migration
chain — the closest thing to production semantics the test pyramid has.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _proposal(seed, *, confidence=0.95, verdict="pass"):
    return {
        "bank_transaction_id": seed["txn_id"],
        "invoice_id": seed["invoice_id"],
        "counterparty_id": seed["party_id"],
        "invoice_number": "INV-A-1",
        "amount_paise": 1_000_000,
        "kind": "full",
        "confidence": confidence,
        "critic_verdict": {"verdict": verdict, "checker": "test"},
        "txn_date": "2026-06-05T00:00:00+00:00",
        "due_date": "2026-05-31T00:00:00+00:00",
    }


async def test_commit_guardrails_full_cycle(seeded):
    from sqlalchemy import select

    from app.db import session_scope
    from app.db.models import Approval, AuditLog, Invoice
    from app.services.recon import route_proposal

    a = seeded["a"]

    # critic fail → rejected outright
    async with session_scope() as session:
        out = await route_proposal(
            session, tenant_id=a["tenant_id"], run_id="r1",
            proposal=_proposal(a, verdict="fail"),
        )
    assert out == {"committed": False, "queued": False, "reason": "critic rejected"}

    # sub-floor but critic-passed → approval queue, not the books
    async with session_scope() as session:
        out = await route_proposal(
            session, tenant_id=a["tenant_id"], run_id="r1",
            proposal=_proposal(a, confidence=0.8),
        )
        assert out["queued"] is True
    async with session_scope() as session:
        approvals = list(await session.scalars(select(Approval)))
        assert len(approvals) == 1 and approvals[0].status == "pending"
        invoice = await session.get(Invoice, a["invoice_id"])
        assert invoice.status == "open"  # nothing posted

    # above floor → committed, invoice paid, audit row written
    async with session_scope() as session:
        out = await route_proposal(
            session, tenant_id=a["tenant_id"], run_id="r1", proposal=_proposal(a)
        )
        assert out["committed"] is True
    async with session_scope() as session:
        invoice = await session.get(Invoice, a["invoice_id"])
        assert invoice.status == "paid"
        audit = list(await session.scalars(select(AuditLog)))
        assert any(r.action == "ledger.commit" for r in audit)

    # double-commit against the same invoice refused
    async with session_scope() as session:
        out = await route_proposal(
            session, tenant_id=a["tenant_id"], run_id="r2", proposal=_proposal(a)
        )
    assert out["committed"] is False and "not open" in out["reason"]


async def test_cross_tenant_isolation(seeded):
    from app.db import session_scope
    from app.db.books_repo import BooksRepo
    from app.db.models import Invoice
    from app.services.recon import route_proposal

    a, b = seeded["a"], seeded["b"]

    async with session_scope() as session:
        repo = BooksRepo(session)
        # tenant A's repo views never include tenant B's rows
        a_txns = await repo.transactions(a["tenant_id"])
        assert {t.id for t in a_txns} == {a["txn_id"]}
        assert await repo.invoice(b["invoice_id"], a["tenant_id"]) is None
        assert await repo.transaction(b["txn_id"], a["tenant_id"]) is None

    # a proposal smuggling tenant B's invoice under tenant A's identity dies
    async with session_scope() as session:
        out = await route_proposal(
            session,
            tenant_id=a["tenant_id"],
            run_id="rx",
            proposal={**_proposal(a), "invoice_id": b["invoice_id"]},
        )
    assert out["committed"] is False and out.get("queued") is not True
    async with session_scope() as session:
        b_invoice = await session.get(Invoice, b["invoice_id"])
        assert b_invoice.status == "open"  # untouched


async def test_audit_chain_detects_tampering(seeded):
    from sqlalchemy import text

    from app.db import session_scope
    from app.services.audit import write_audit
    from app.services.dataroom import verify_audit_chain

    a = seeded["a"]
    async with session_scope() as session:
        for i in range(3):
            await write_audit(
                session,
                tenant_id=a["tenant_id"],
                actor={"kind": "user", "id": a["user_id"]},
                action=f"test.event_{i}",
                entity_ref=f"thing:{i}",
                payload={"i": i},
            )
    async with session_scope() as session:
        assert (await verify_audit_chain(session, a["tenant_id"]))["ok"] is True

    # tamper with the middle row's payload after the fact
    async with session_scope() as session:
        await session.execute(
            text(
                "UPDATE audit_log SET payload = '{\"i\": 999}'::json "
                "WHERE action = 'test.event_1'"
            )
        )
    async with session_scope() as session:
        result = await verify_audit_chain(session, a["tenant_id"])
    assert result["ok"] is False
    assert result["first_break_index"] is not None
