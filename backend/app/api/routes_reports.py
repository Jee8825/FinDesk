"""Month-end report pack API (A8)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.auth.deps import Auth
from app.db import session_scope
from app.services.reports import month_end_report

router = APIRouter(tags=["books"])


@router.get("/reports/month-end")
async def get_month_end(auth: Auth, period: str) -> dict[str, Any]:
    try:
        async with session_scope() as session:
            return await month_end_report(session, auth.tenant_id, period)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"bad period (want YYYY-MM): {exc}"
        ) from exc
