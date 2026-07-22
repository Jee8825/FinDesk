"""B5 data room API — owner view + expiring read-only lender share links."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import APIRouter, HTTPException, status

from app.auth.deps import Auth
from app.auth.security import ALGORITHM
from app.config import get_settings
from app.db import session_scope
from app.services.audit import write_audit
from app.services.dataroom import build_dataroom

router = APIRouter(tags=["cash"])

SHARE_TTL_DAYS = 7


@router.get("/dataroom")
async def dataroom(auth: Auth) -> dict[str, Any]:
    async with session_scope() as session:
        return await build_dataroom(session, auth.tenant_id)


@router.post("/dataroom/share")
async def create_share(auth: Auth) -> dict[str, Any]:
    if auth.role not in {"owner", "ca"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only owner/CA can share the data room")
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "typ": "dataroom_share",
            "ten": auth.tenant_id,
            "by": auth.user_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=SHARE_TTL_DAYS)).timestamp()),
        },
        get_settings().jwt_secret,
        algorithm=ALGORITHM,
    )
    async with session_scope() as session:
        await write_audit(
            session,
            tenant_id=auth.tenant_id,
            actor={"kind": "user", "id": auth.user_id},
            action="dataroom.shared",
            entity_ref=f"tenant:{auth.tenant_id}",
            payload={"expires_in_days": SHARE_TTL_DAYS},
        )
    return {"share_token": token, "expires_in_days": SHARE_TTL_DAYS}


@router.get("/dataroom/shared")
async def shared_view(token: str) -> dict[str, Any]:
    """Lender-facing read-only view. Signed token is the only credential."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
        if payload.get("typ") != "dataroom_share":
            raise jwt.InvalidTokenError("not a share token")
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired link") from exc
    async with session_scope() as session:
        room = await build_dataroom(session, payload["ten"])
    room["shared"] = {"read_only": True, "expires_at": payload["exp"]}
    return room


@router.get("/audit/verify")
async def audit_verify(auth: Auth) -> dict[str, Any]:
    """Recompute the tenant's hash-chained audit log live — tamper-evidence on demand."""
    from app.services.audit import verify_chain

    async with session_scope() as session:
        return await verify_chain(session, auth.tenant_id)
