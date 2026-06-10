"""Approval queue API — the human side of maker–checker."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.deps import Auth
from app.db import session_scope
from app.services.approvals import decide_approval, list_approvals

router = APIRouter(tags=["approvals"])

DECIDER_ROLES = {"owner", "accountant", "ca"}


class ApprovalOut(BaseModel):
    id: str
    action_kind: str
    action_payload: dict[str, Any]
    policy_verdicts: dict[str, Any]
    requested_by: dict[str, Any]
    status: str
    created_at: str
    rationale: str | None = None


class DecideRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    rationale: str | None = Field(default=None, max_length=500)


@router.get("/approvals", response_model=list[ApprovalOut])
async def get_approvals(auth: Auth, status_filter: str | None = "pending") -> list[ApprovalOut]:
    async with session_scope() as session:
        rows = await list_approvals(session, auth.tenant_id, status_filter)
        return [
            ApprovalOut(
                id=a.id,
                action_kind=a.action_kind,
                action_payload=a.action_payload,
                policy_verdicts=a.policy_verdicts,
                requested_by=a.requested_by,
                status=a.status,
                created_at=a.created_at.isoformat(),
                rationale=a.rationale,
            )
            for a in rows
        ]


@router.post("/approvals/{approval_id}/decide")
async def decide(approval_id: str, body: DecideRequest, auth: Auth) -> dict[str, Any]:
    if auth.role not in DECIDER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot decide approvals")
    async with session_scope() as session:
        result = await decide_approval(
            session,
            tenant_id=auth.tenant_id,
            approval_id=approval_id,
            decision=body.decision,
            decider_id=auth.user_id,
            rationale=body.rationale,
        )
    if not result.get("ok"):
        raise HTTPException(status.HTTP_409_CONFLICT, result.get("reason", "cannot decide"))
    return result
