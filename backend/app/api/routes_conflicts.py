"""Conflict cards API — list (with lazy engine sync) and one-tap resolve."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.deps import Auth
from app.db import session_scope
from app.services.conflicts import list_open_conflicts, resolve_conflict, sync_conflicts

router = APIRouter(tags=["conflicts"])

RESOLVER_ROLES = {"owner", "accountant", "ca"}


class ConflictOut(BaseModel):
    id: str
    claim_kind: str
    scope_key: str
    claim_a: dict[str, Any]
    claim_b: dict[str, Any]
    engine_view: dict[str, Any]
    status: str
    created_at: str


class ResolveRequest(BaseModel):
    winner: str = Field(pattern="^(a|b)$")
    rationale: str | None = Field(default=None, max_length=500)


@router.get("/conflicts", response_model=list[ConflictOut])
async def get_conflicts(auth: Auth) -> list[ConflictOut]:
    async with session_scope() as session:
        await sync_conflicts(session, auth.tenant_id)
        rows = await list_open_conflicts(session, auth.tenant_id)
        return [
            ConflictOut(
                id=c.id,
                claim_kind=c.claim_kind,
                scope_key=c.scope_key,
                claim_a=c.claim_a,
                claim_b=c.claim_b,
                engine_view=c.engine_view,
                status=c.status,
                created_at=c.created_at.isoformat(),
            )
            for c in rows
        ]


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve(conflict_id: str, body: ResolveRequest, auth: Auth) -> dict[str, Any]:
    if auth.role not in RESOLVER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot resolve conflicts")
    async with session_scope() as session:
        result = await resolve_conflict(
            session,
            tenant_id=auth.tenant_id,
            conflict_id=conflict_id,
            winner=body.winner,
            resolver_id=auth.user_id,
            rationale=body.rationale,
        )
    if not result.get("ok"):
        raise HTTPException(status.HTTP_409_CONFLICT, result.get("reason", "cannot resolve"))
    return result
