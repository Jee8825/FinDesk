"""Approval engine — queue, hash-bound single-use tokens, decisions.

Maker–checker: agents request, humans decide. The action payload is hashed at
request time; the decision re-hashes the stored payload before executing, so a
mutated payload can never ride an old approval (no approve-then-mutate). The
minted token is single-use and recorded in the audit chain.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from findesk_shared import uuid7
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Approval
from app.services.audit import write_audit


def action_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def queue_approval(
    session: AsyncSession,
    *,
    tenant_id: str,
    action_kind: str,
    action_payload: dict[str, Any],
    requested_by: dict[str, Any],
    policy_verdicts: dict[str, Any],
) -> Approval:
    approval = Approval(
        id=uuid7(),
        tenant_id=tenant_id,
        action_kind=action_kind,
        action_payload=action_payload,
        action_hash=action_hash(action_payload),
        requested_by=requested_by,
        policy_verdicts=policy_verdicts,
        status="pending",
    )
    session.add(approval)
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor=requested_by,
        action="approval.requested",
        entity_ref=f"approval:{approval.id}",
        payload={"action_kind": action_kind, "action_hash": approval.action_hash,
                 "policy_verdicts": policy_verdicts},
    )
    return approval


async def list_approvals(
    session: AsyncSession, tenant_id: str, status: str | None = "pending"
) -> list[Approval]:
    q = select(Approval).where(Approval.tenant_id == tenant_id)
    if status:
        q = q.where(Approval.status == status)
    q = q.order_by(Approval.created_at.desc()).limit(200)
    return list(await session.scalars(q))


async def decide_approval(
    session: AsyncSession,
    *,
    tenant_id: str,
    approval_id: str,
    decision: str,  # "approved" | "rejected"
    decider_id: str,
    rationale: str | None = None,
) -> dict[str, Any]:
    approval = await session.scalar(
        select(Approval).where(Approval.id == approval_id, Approval.tenant_id == tenant_id)
    )
    if approval is None:
        return {"ok": False, "reason": "not found"}
    if approval.status != "pending":
        return {"ok": False, "reason": f"already {approval.status}"}
    if action_hash(approval.action_payload) != approval.action_hash:
        approval.status = "expired"
        return {"ok": False, "reason": "action hash mismatch — payload changed since request"}

    approval.status = decision
    approval.decider_id = decider_id
    approval.decided_at = datetime.now(UTC)
    approval.rationale = rationale
    token_id = uuid7() if decision == "approved" else None
    approval.token_id = token_id

    await write_audit(
        session,
        tenant_id=tenant_id,
        actor={"kind": "user", "id": decider_id},
        action=f"approval.{decision}",
        entity_ref=f"approval:{approval.id}",
        payload={
            "action_kind": approval.action_kind,
            "action_hash": approval.action_hash,
            "token_id": token_id,
            "rationale": rationale,
        },
    )

    result: dict[str, Any] = {"ok": True, "status": decision, "token_id": token_id}
    if decision == "approved" and approval.action_kind == "send_email":
        from findesk_tools.email import EmailDraft, SandboxEmailProvider

        from app import memoryclient
        from app.config import get_settings

        payload = approval.action_payload
        draft = EmailDraft(
            to=payload["to"],
            subject=payload["subject"],
            body_md=payload["body_md"],
            thread_ref=payload.get("thread_ref"),
        )
        # token consumed here: it exists only for this send and is recorded on
        # the message, the approval row, and the audit chain
        receipt = SandboxEmailProvider(get_settings().outbox_dir).send(
            tenant_id=tenant_id, draft=draft, approval_token=token_id
        )
        await write_audit(
            session,
            tenant_id=tenant_id,
            actor={"kind": "user", "id": decider_id},
            action="email.sent",
            entity_ref=f"invoice:{payload.get('invoice_id')}",
            payload={
                "message_id": receipt.message_id,
                "provider": receipt.provider,
                "to": payload["to"],
                "subject": payload["subject"],
                "tone": payload.get("tone"),
                "approval_id": approval.id,
                "token_id": token_id,
            },
        )
        await memoryclient.remember(
            tenant_id=tenant_id,
            scope_key=f"client:{payload.get('counterparty_id')}",
            session_id=approval.requested_by.get("run_id") or f"approval:{approval.id}",
            content=(
                f"A {payload.get('tone', 'neutral')} payment reminder for invoice "
                f"{payload.get('invoice_number')} was sent on approval "
                f"({payload.get('days_overdue')} days overdue at the time)."
            ),
        )
        result["execution"] = {"sent": True, "message_id": receipt.message_id}
    if decision == "approved" and approval.action_kind == "commit_match":
        from app.services.recon import commit_proposal  # local import: avoids cycle

        run_id = approval.requested_by.get("run_id", "")
        proposal = approval.action_payload
        outcome = await commit_proposal(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            proposal=proposal,
            matched_by="human",
            approval_id=approval.id,
        )
        result["execution"] = outcome
        if outcome.get("committed"):
            from findesk_shared import format_inr

            from app import memoryclient

            session_id = run_id or f"approval:{approval.id}"
            scope_key = f"client:{proposal['counterparty_id']}"
            # payment-timing observation (B1 feedstock) — the run-side learn
            # node only covers auto-commits; approvals learn here
            try:
                paid = datetime.fromisoformat(proposal["txn_date"]).date()
                due = datetime.fromisoformat(proposal["due_date"]).date()
                delta = (paid - due).days
                timing = f"{delta} days late" if delta > 0 else f"{-delta} days early"
                await memoryclient.remember(
                    tenant_id=tenant_id,
                    scope_key=scope_key,
                    session_id=session_id,
                    content=(
                        f"Invoice {proposal.get('invoice_number')} "
                        f"({format_inr(int(proposal['amount_paise']))}) was paid {timing} "
                        f"relative to its due date {due.isoformat()}."
                    ),
                )
            except (KeyError, ValueError):
                pass  # older payloads without dates — nothing to learn
            if proposal.get("kind") == "tds_adjusted":
                # the human just confirmed a deduction pattern — remember it
                rate_pct = int(proposal.get("tds_bps", 0)) / 100
                await memoryclient.remember(
                    tenant_id=tenant_id,
                    scope_key=scope_key,
                    session_id=session_id,
                    content=(
                        f"This client deducts {rate_pct:g}% TDS on payments — confirmed by "
                        f"human approval on invoice {proposal.get('invoice_number')}."
                    ),
                )
    return result
