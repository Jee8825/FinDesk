"""Reconciliation commit service — the only path that posts matches to the books.

Guardrail P3 (deterministic, outside any LLM loop): a proposal auto-commits
only if (a) amounts balance exactly — for ``tds_adjusted``, payment + TDS must
equal the invoice to the paisa, (b) the invoice is open and not already
matched, (c) the critic verdict is pass, (d) confidence ≥ the floor. A
proposal that passes the critic but sits below the floor is **queued for
human approval** (maker–checker); everything else is rejected with a reason.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from findesk_shared import uuid7
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.books_repo import BooksRepo
from app.db.models import LedgerEntry, Match
from app.services.audit import write_audit

CONFIDENCE_FLOOR = 0.9  # policy YAML in a later slice; constant until then


def _balance_problem(proposal: dict[str, Any], invoice_amount_paise: int) -> str | None:
    amount = int(proposal["amount_paise"])
    if proposal.get("kind") == "tds_adjusted":
        tds = int(proposal.get("tds_paise", 0))
        if tds <= 0:
            return "tds_adjusted without tds_paise"
        if amount + tds != invoice_amount_paise:
            return "payment + TDS does not equal invoice"
        return None
    if amount != invoice_amount_paise:
        return "amounts do not balance"
    return None


async def _validate(
    repo: BooksRepo, *, tenant_id: str, proposal: dict[str, Any]
) -> tuple[Any | None, str | None]:
    """Shared deterministic checks. Returns (invoice, problem)."""
    invoice = await repo.invoice(proposal["invoice_id"], tenant_id)
    if invoice is None or invoice.status != "open":
        return None, "invoice not open"
    if await repo.committed_match_for_target(proposal["invoice_id"]) is not None:
        return None, "invoice already matched"
    if proposal.get("critic_verdict", {}).get("verdict") != "pass":
        return None, "critic rejected"
    problem = _balance_problem(proposal, invoice.amount_paise)
    if problem:
        return None, problem
    return invoice, None


async def commit_proposal(
    session: AsyncSession,
    *,
    tenant_id: str,
    run_id: str,
    proposal: dict[str, Any],
    matched_by: str = "agent",
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Commit one validated proposal. Returns {committed, reason, match_id?}.

    ``matched_by="human"`` (with ``approval_id``) is the approval-queue path:
    the human decision substitutes for the confidence floor; every other check
    still applies — an approval cannot force unbalanced books.
    """
    repo = BooksRepo(session)
    invoice, problem = await _validate(repo, tenant_id=tenant_id, proposal=proposal)
    if problem:
        return {"committed": False, "reason": problem}
    confidence = float(proposal["confidence"])
    if matched_by != "human" and confidence < CONFIDENCE_FLOOR:
        return {"committed": False, "reason": f"confidence {confidence} below floor"}

    txn_id = proposal["bank_transaction_id"]
    amount = int(proposal["amount_paise"])
    tds = int(proposal.get("tds_paise", 0))

    match = Match(
        id=uuid7(),
        tenant_id=tenant_id,
        bank_transaction_id=txn_id,
        target_kind="invoice",
        target_id=invoice.id,
        kind=proposal.get("kind", "full"),
        confidence=confidence,
        matched_by=matched_by,
        critic_verdict=proposal.get("critic_verdict", {}),
        status="committed",
    )
    await repo.add_match(match)
    await repo.set_transaction_matched(txn_id)
    await repo.set_invoice_paid(invoice.id)

    lines = [{"account": "bank", "amount_paise": amount}]
    if tds:
        # TDS deducted by the payer sits as a receivable from the tax dept
        lines.append({"account": "tds_receivable", "amount_paise": tds})
    lines.append({"account": "accounts_receivable", "amount_paise": -invoice.amount_paise})

    entry = LedgerEntry(
        id=uuid7(),
        tenant_id=tenant_id,
        entry_date=datetime.now(UTC),
        lines=lines,
        origin={"kind": "match", "match_id": match.id, "run_id": run_id},
    )
    await repo.add_ledger_entry(entry)

    await write_audit(
        session,
        tenant_id=tenant_id,
        actor=(
            {"kind": "human_approval", "approval_id": approval_id, "run_id": run_id}
            if matched_by == "human"
            else {"kind": "agent", "run_id": run_id}
        ),
        action="ledger.commit",
        entity_ref=f"match:{match.id}",
        payload={
            "bank_transaction_id": txn_id,
            "invoice_id": invoice.id,
            "invoice_number": invoice.number,
            "amount_paise": amount,
            "tds_paise": tds or None,
            "kind": proposal.get("kind", "full"),
            "confidence": confidence,
            "critic": proposal.get("critic_verdict", {}),
            "ledger_entry_id": entry.id,
            "approval_id": approval_id,
        },
    )
    return {"committed": True, "reason": "ok", "match_id": match.id}


async def route_proposal(
    session: AsyncSession, *, tenant_id: str, run_id: str, proposal: dict[str, Any]
) -> dict[str, Any]:
    """Auto-commit above the floor; queue critic-passed sub-floor proposals."""
    from app.services.approvals import queue_approval  # local import: avoids cycle

    repo = BooksRepo(session)
    invoice, problem = await _validate(repo, tenant_id=tenant_id, proposal=proposal)
    if problem:
        return {"committed": False, "queued": False, "reason": problem}
    if float(proposal["confidence"]) >= CONFIDENCE_FLOOR:
        outcome = await commit_proposal(
            session, tenant_id=tenant_id, run_id=run_id, proposal=proposal
        )
        return {**outcome, "queued": False}
    approval = await queue_approval(
        session,
        tenant_id=tenant_id,
        action_kind="commit_match",
        action_payload=proposal,
        requested_by={"kind": "agent", "run_id": run_id},
        policy_verdicts={
            "critic": proposal.get("critic_verdict", {}).get("verdict"),
            "confidence": proposal["confidence"],
            "floor": CONFIDENCE_FLOOR,
            "rule": "below confidence floor → human approval",
        },
    )
    return {"committed": False, "queued": True, "reason": "queued", "approval_id": approval.id}
