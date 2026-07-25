"""LeakRadar API — the leak table, usage confirmation, and gated vendor emails.

Nothing here sends anything. `POST /leaks/{id}/action` queues a maker-checker
approval carrying the draft the scan already wrote; the send happens inside
decide_approval with a single-use token, identically to collections chasers.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.deps import Auth
from app.db import session_scope
from app.memoryclient import remember
from app.services.approvals import queue_approval
from app.services.leaks import (
    CA_NOTE,
    list_leaks,
    mode_for,
    set_usage,
    totals,
)

router = APIRouter(tags=["leaks"])

REQUESTER_ROLES = {"owner", "accountant", "ca"}


class LeakRow(BaseModel):
    id: str
    vendor_slug: str
    vendor_label: str
    category_code: str | None
    cadence: str
    period_days: int
    periods_per_year: int | None
    occurrences: int
    confidence: float
    first_seen: str
    last_seen: str
    next_expected: str
    status: str
    amount_paise: int
    latest_amount_paise: int
    run_rate_paise: int
    drift_kind: str | None
    drift_paise_per_year: int
    duplicate_paise: int
    leak_score: int
    score_components: dict[str, Any]
    recoverable_paise_per_year: int
    reason: str
    recommended_action: str
    narrative: str | None
    usage: str | None
    usage_confirmed_at: str | None
    has_draft: bool


class LeakListOut(BaseModel):
    rows: list[LeakRow]
    totals: dict[str, Any]
    mode: str
    note: str


def _out(s: Any) -> LeakRow:
    return LeakRow(
        id=s.id,
        vendor_slug=s.vendor_slug,
        vendor_label=s.vendor_label,
        category_code=s.category_code,
        cadence=s.cadence,
        period_days=s.period_days,
        periods_per_year=s.periods_per_year,
        occurrences=s.occurrences,
        confidence=s.confidence,
        first_seen=s.first_seen.isoformat(),
        last_seen=s.last_seen.isoformat(),
        next_expected=s.next_expected.isoformat(),
        status=s.status,
        amount_paise=s.amount_paise,
        latest_amount_paise=s.latest_amount_paise,
        run_rate_paise=s.run_rate_paise,
        drift_kind=s.drift_kind,
        drift_paise_per_year=s.drift_paise_per_year,
        duplicate_paise=s.duplicate_paise,
        leak_score=s.leak_score,
        score_components=s.score_components or {},
        recoverable_paise_per_year=s.recoverable_paise_per_year,
        reason=s.reason,
        recommended_action=s.recommended_action,
        narrative=s.narrative,
        usage=s.usage,
        usage_confirmed_at=(
            s.usage_confirmed_at.isoformat() if s.usage_confirmed_at else None
        ),
        has_draft=bool(s.draft),
    )


@router.get("/leaks", response_model=LeakListOut)
async def leaks(auth: Auth) -> LeakListOut:
    async with session_scope() as session:
        rows = await list_leaks(session, tenant_id=auth.tenant_id)
        return LeakListOut(
            rows=[_out(r) for r in rows],
            totals=totals(rows),
            mode=await mode_for(session, auth.tenant_id),
            note=CA_NOTE,
        )


class UsageIn(BaseModel):
    usage: str = Field(pattern="^(in_use|unused)$")


@router.post("/leaks/{subscription_id}/usage")
async def confirm_usage(
    subscription_id: str, body: UsageIn, auth: Auth
) -> dict[str, Any]:
    """Record whether the user still uses this — the one signal bank data lacks.

    Written to Recall as well as the row, so it decays and gets re-asked instead
    of being trusted indefinitely.
    """
    if auth.role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "viewers cannot confirm usage")
    async with session_scope() as session:
        result = await set_usage(
            session,
            tenant_id=auth.tenant_id,
            subscription_id=subscription_id,
            usage=body.usage,
            actor_id=auth.user_id,
        )
    if not result["ok"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, result["reason"])

    # best-effort: the row is already authoritative, memory makes it decay
    await remember(
        tenant_id=auth.tenant_id,
        scope_key=f"vendor:{result['vendor_slug']}",
        session_id=f"usage:{subscription_id}",
        content=result["memory_content"],
    )
    return result


class ActionIn(BaseModel):
    kind: str = Field(pattern="^(cancel|renegotiate|downgrade)$")


@router.post("/leaks/{subscription_id}/action", status_code=status.HTTP_202_ACCEPTED)
async def request_action(
    subscription_id: str, body: ActionIn, auth: Auth
) -> dict[str, Any]:
    """Queue a vendor email for approval. Never sends."""
    if auth.role not in REQUESTER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot request actions")

    from sqlalchemy import select

    from app.db.models import Subscription

    async with session_scope() as session:
        row = await session.scalar(
            select(Subscription).where(
                Subscription.id == subscription_id,
                Subscription.tenant_id == auth.tenant_id,
            )
        )
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "subscription not found")
        if not row.draft:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "no draft on this row yet — run the leak scan first",
            )
        approval = await queue_approval(
            session,
            tenant_id=auth.tenant_id,
            action_kind="send_email",
            requested_by={"kind": "user", "id": auth.user_id},
            action_payload={
                "to": [],  # vendor contact is supplied by the approver
                "subject": row.draft["subject"],
                "body": row.draft["body"],
                "reason": (
                    f"LeakRadar {body.kind}: {row.vendor_label} — "
                    f"{row.recommended_action}"
                ),
                "subscription_id": row.id,
                "vendor_slug": row.vendor_slug,
            },
            policy_verdicts={
                "source": "leakradar",
                "action_kind": body.kind,
                "recoverable_paise_per_year": row.recoverable_paise_per_year,
                "drafted_by": (row.draft or {}).get("by", "unknown"),
                # stated so an approver knows the recipient is still blank
                "recipient_required": True,
            },
        )
        approval_id = approval.id
    return {"ok": True, "approval_id": approval_id, "kind": body.kind}
