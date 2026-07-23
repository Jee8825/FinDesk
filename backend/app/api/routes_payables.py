"""Buyer-side payables compliance — §15 clock + 43B(h) exposure per MSE bill.

The mirror of the receivables radar: same statutory engine, opposite
direction. Router stays thin; math + gathering live in services/payables.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import Auth
from app.config import get_settings
from app.db import session_scope
from app.db.models import Forecast
from app.services.payables import CA_NOTE, defense_plan, gather_items, totals

router = APIRouter(tags=["cash"])


class PayableItem(BaseModel):
    bill_id: str
    bill_number: str
    vendor: str
    msme_status: str
    amount_paise: int  # original bill amount
    outstanding_paise: int  # unpaid portion — the clock runs on this
    clock: dict[str, Any]


class PayablesOut(BaseModel):
    items: list[PayableItem]
    totals: dict[str, int]
    non_mse_open_count: int
    ca_note: str


class PlanOut(BaseModel):
    items: list[dict[str, Any]]
    totals: dict[str, int]
    cash_basis_paise: int | None
    ca_note: str


@router.get("/payables/compliance", response_model=PayablesOut)
async def payables_compliance(auth: Auth) -> PayablesOut:
    now = datetime.now(UTC)
    async with session_scope() as session:
        items, rows, amounts, non_mse = await gather_items(
            session, auth.tenant_id, now, bank_rate_bps=get_settings().statutory_bank_rate_bps
        )
    return PayablesOut(
        items=[PayableItem(**i) for i in items],
        totals=totals(rows, amounts),
        non_mse_open_count=non_mse,
        ca_note=CA_NOTE,
    )


@router.get("/payables/plan", response_model=PlanOut)
async def payables_plan(auth: Auth) -> PlanOut:
    """Deduction Defense — ranked pay-first plan over breached/closing bills."""
    now = datetime.now(UTC)
    async with session_scope() as session:
        items, _rows, _amounts, _ = await gather_items(
            session, auth.tenant_id, now, bank_rate_bps=get_settings().statutory_bank_rate_bps
        )
        latest = await session.scalar(
            select(Forecast)
            .where(Forecast.tenant_id == auth.tenant_id)
            .order_by(Forecast.created_at.desc())
            .limit(1)
        )
    plan = defense_plan(
        [i for i in items if i["clock"]["band"] in {"closing", "breached"}],
        cash_available_paise=latest.opening_balance_paise if latest else None,
    )
    return PlanOut(**plan, ca_note=CA_NOTE)
