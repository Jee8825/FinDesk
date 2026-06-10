"""Reconciliation commit service — the only path that posts matches to the books.

Guardrail P3 (deterministic, outside any LLM loop): a proposal is committed
only if (a) amounts balance exactly, (b) the invoice is open and not already
matched, (c) the critic verdict is pass, (d) confidence ≥ the floor. Everything
else stays an exception for the human queue.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from findesk_shared import uuid7
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.books_repo import BooksRepo
from app.db.models import LedgerEntry, Match
from app.services.audit import write_audit

CONFIDENCE_FLOOR = 0.9  # policy YAML in Phase 2; constant until then


async def commit_proposal(
    session: AsyncSession,
    *,
    tenant_id: str,
    run_id: str,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """Commit one match proposal. Returns {committed: bool, reason, match_id?}."""
    repo = BooksRepo(session)
    txn_id = proposal["bank_transaction_id"]
    invoice_id = proposal["invoice_id"]
    confidence = float(proposal["confidence"])
    verdict = proposal.get("critic_verdict", {})

    invoice = await repo.invoice(invoice_id, tenant_id)
    if invoice is None or invoice.status != "open":
        return {"committed": False, "reason": "invoice not open"}
    if await repo.committed_match_for_target(invoice_id) is not None:
        return {"committed": False, "reason": "invoice already matched"}
    if verdict.get("verdict") != "pass":
        return {"committed": False, "reason": "critic rejected"}
    if confidence < CONFIDENCE_FLOOR:
        return {"committed": False, "reason": f"confidence {confidence} below floor"}
    if int(proposal["amount_paise"]) != invoice.amount_paise:
        return {"committed": False, "reason": "amounts do not balance"}

    match = Match(
        id=uuid7(),
        tenant_id=tenant_id,
        bank_transaction_id=txn_id,
        target_kind="invoice",
        target_id=invoice_id,
        kind=proposal.get("kind", "full"),
        confidence=confidence,
        matched_by="agent",
        critic_verdict=verdict,
        status="committed",
    )
    await repo.add_match(match)
    await repo.set_transaction_matched(txn_id)
    await repo.set_invoice_paid(invoice_id)

    entry = LedgerEntry(
        id=uuid7(),
        tenant_id=tenant_id,
        entry_date=datetime.now(UTC),
        lines=[
            {"account": "bank", "amount_paise": invoice.amount_paise},
            {"account": "accounts_receivable", "amount_paise": -invoice.amount_paise},
        ],
        origin={"kind": "match", "match_id": match.id, "run_id": run_id},
    )
    await repo.add_ledger_entry(entry)

    await write_audit(
        session,
        tenant_id=tenant_id,
        actor={"kind": "agent", "run_id": run_id},
        action="ledger.commit",
        entity_ref=f"match:{match.id}",
        payload={
            "bank_transaction_id": txn_id,
            "invoice_id": invoice_id,
            "invoice_number": invoice.number,
            "amount_paise": invoice.amount_paise,
            "confidence": confidence,
            "critic": verdict,
            "ledger_entry_id": entry.id,
        },
    )
    return {"committed": True, "reason": "ok", "match_id": match.id}
