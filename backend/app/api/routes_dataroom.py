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


@router.get("/dataroom/export")
async def dataroom_export(auth: Auth):
    """Credit pack as a zip — summary.md + aging/compliance/forecast CSVs.

    Deterministic files only; the audit head hash inside summary.md lets a
    lender verify the pack against the live chain.
    """
    from datetime import datetime as _dt

    from fastapi.responses import Response
    from sqlalchemy import select

    from app.config import get_settings as _gs
    from app.db.books_repo import BooksRepo
    from app.db.models import Forecast, ForecastLine
    from app.services.clocks import recompute_clocks
    from app.services.dataroom_export import build_pack
    from app.services.payables import gather_items

    now = _dt.now(UTC)
    async with session_scope() as session:
        room = await build_dataroom(session, auth.tenant_id)
        parties = {
            c.id: c.name for c in await BooksRepo(session).counterparties(auth.tenant_id)
        }
        clock_rows = await recompute_clocks(session, auth.tenant_id)
        receivables = [
            {
                "invoice_number": inv.number,
                "client": parties.get(inv.counterparty_id, "?"),
                "amount_paise": inv.amount_paise,
                "clock": snap,
            }
            for inv, _clock, snap in clock_rows
        ]
        payable_items, _r, _a, _n = await gather_items(
            session, auth.tenant_id, now, bank_rate_bps=_gs().statutory_bank_rate_bps
        )
        latest = await session.scalar(
            select(Forecast)
            .where(Forecast.tenant_id == auth.tenant_id)
            .order_by(Forecast.created_at.desc())
            .limit(1)
        )
        weeks: list[dict[str, Any]] = []
        if latest is not None:
            lines = await session.scalars(
                select(ForecastLine)
                .where(ForecastLine.forecast_id == latest.id)
                .order_by(ForecastLine.scenario, ForecastLine.week)
            )
            weeks = [
                {
                    "week": ln.week,
                    "week_start": ln.week_start,
                    "scenario": ln.scenario,
                    "inflow_paise": ln.inflow_paise,
                    "outflow_paise": ln.outflow_paise,
                    "closing_paise": ln.closing_paise,
                }
                for ln in lines
            ]

    pack = build_pack(
        room=room, receivables=receivables, payables=payable_items, forecast_weeks=weeks
    )
    stamp = now.date().isoformat()
    return Response(
        content=pack,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="findesk-credit-pack-{stamp}.zip"'
        },
    )
