"""Month-end close API (F2) — checklist, maker-checker sign-off, close pack."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth.deps import Auth
from app.config import get_settings
from app.db import session_scope
from app.services.close import build_checklist, checklist_md, sign_off

router = APIRouter(tags=["close"])

SIGNER_ROLES = {"owner", "accountant", "ca"}


def _period(period: str | None, now: datetime) -> str:
    return period or now.strftime("%Y-%m")


@router.get("/close/checklist")
async def checklist(auth: Auth, period: str | None = None) -> dict[str, Any]:
    now = datetime.now(UTC)
    async with session_scope() as session:
        result = await build_checklist(
            session,
            tenant_id=auth.tenant_id,
            now=now,
            bank_rate_bps=get_settings().statutory_bank_rate_bps,
        )
    return {"period": _period(period, now), **result}


class SignoffBody(BaseModel):
    period: str | None = None
    rationale: str | None = Field(default=None, max_length=500)


@router.post("/close/signoff")
async def signoff(body: SignoffBody, auth: Auth) -> dict[str, Any]:
    if auth.role not in SIGNER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot sign off a close")
    now = datetime.now(UTC)
    async with session_scope() as session:
        result = await build_checklist(
            session,
            tenant_id=auth.tenant_id,
            now=now,
            bank_rate_bps=get_settings().statutory_bank_rate_bps,
        )
        if not result["ready"]:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"close blocked: {', '.join(result['blockers'])}",
            )
        if result["warnings"] and not (body.rationale and body.rationale.strip()):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "warnings present — a rationale is required to sign off past them",
            )
        return await sign_off(
            session,
            tenant_id=auth.tenant_id,
            period=_period(body.period, now),
            checklist=result,
            decider_id=auth.user_id,
            rationale=body.rationale,
        )


@router.get("/close/pack")
async def close_pack(auth: Auth, period: str | None = None) -> Response:
    """Close-pack zip: the credit pack + close_checklist.md — deterministic,
    a CA can regenerate and diff it."""
    from app.api.routes_dataroom import build_export_payload
    from app.services.dataroom_export import build_pack

    now = datetime.now(UTC)
    async with session_scope() as session:
        payload = await build_export_payload(session, auth)
        checklist_data = await build_checklist(
            session,
            tenant_id=auth.tenant_id,
            now=now,
            bank_rate_bps=get_settings().statutory_bank_rate_bps,
        )
    eff_period = _period(period, now)
    blob = build_pack(
        **payload,
        extra_files={"close_checklist.md": checklist_md(eff_period, checklist_data)},
    )
    return Response(
        content=blob,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="findesk-close-{eff_period}.zip"'
        },
    )
