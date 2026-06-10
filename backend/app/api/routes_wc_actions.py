"""B4 working-capital actions API — list ranked options, request approval.

Requesting approval moves the action into the standard queue; the decide path
executes TReDS listings through the token-gated tool (see services/approvals).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import Auth
from app.db import session_scope
from app.db.models import WcAction
from app.services.approvals import queue_approval

router = APIRouter(tags=["cash"])

REQUESTER_ROLES = {"owner", "accountant", "ca"}


class WcActionOut(BaseModel):
    id: str
    kind: str
    invoice_number: str
    client: str
    unlock_paise: int
    cost_paise: int
    rank: int
    detail: dict[str, Any]
    status: str


@router.get("/wc-actions", response_model=list[WcActionOut])
async def list_actions(auth: Auth) -> list[WcActionOut]:
    async with session_scope() as session:
        rows = await session.scalars(
            select(WcAction)
            .where(
                WcAction.tenant_id == auth.tenant_id,
                WcAction.status.in_(("proposed", "approval_requested", "executed")),
            )
            .order_by(WcAction.rank)
        )
        return [
            WcActionOut(
                id=a.id,
                kind=a.kind,
                invoice_number=a.invoice_number,
                client=a.client,
                unlock_paise=a.unlock_paise,
                cost_paise=a.cost_paise,
                rank=a.rank,
                detail=a.detail,
                status=a.status,
            )
            for a in rows
        ]


@router.post("/wc-actions/{action_id}/request")
async def request_approval(action_id: str, auth: Auth) -> dict[str, Any]:
    if auth.role not in REQUESTER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot request actions")
    async with session_scope() as session:
        action = await session.scalar(
            select(WcAction).where(
                WcAction.id == action_id, WcAction.tenant_id == auth.tenant_id
            )
        )
        if action is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "action not found")
        if action.status != "proposed":
            raise HTTPException(status.HTTP_409_CONFLICT, f"already {action.status}")
        if action.kind != "treds":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "only treds actions execute via approval; collect runs through collections",
            )
        approval = await queue_approval(
            session,
            tenant_id=auth.tenant_id,
            action_kind="treds_listing",
            action_payload={
                "wc_action_id": action.id,
                "invoice_id": action.invoice_id,
                "invoice_number": action.invoice_number,
                "client": action.client,
                "unlock_paise": action.unlock_paise,
                "cost_paise": action.cost_paise,
                "quote": action.detail.get("quote", {}),
            },
            requested_by={"kind": "user", "id": auth.user_id, "run_id": action.run_id},
            policy_verdicts={
                "rule": "receivable discounting is always human-gated (P1/P2)",
                "cost_paise": action.cost_paise,
                "unlock_paise": action.unlock_paise,
            },
        )
        action.status = "approval_requested"
        action.approval_id = approval.id
    return {"ok": True, "approval_id": approval.id}
