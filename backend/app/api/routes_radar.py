"""B2 receivables radar — statutory clocks + B1 payment predictions.

Reading the radar recomputes and persists every open invoice's clock (the
enforcer graph will consume rung *transitions* from these rows). Predictions
come from remembered payment behavior; statutory figures are engine-computed
and ship with explicit review-with-your-CA framing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from findesk_shared import parse_late_days, uuid7
from pydantic import BaseModel
from sqlalchemy import select

from app import memoryclient
from app.auth.deps import Auth
from app.db import session_scope
from app.db.books_repo import BooksRepo
from app.db.models import StatutoryClock
from app.services.statutory import clock_snapshot

router = APIRouter(tags=["cash"])

CA_NOTE = (
    "Interest figures are computed under MSME Act §16 (3× bank rate, monthly "
    "rests) as preparation only — review with your CA before any demand."
)


class RadarItem(BaseModel):
    invoice_id: str
    invoice_number: str
    client: str
    amount_paise: int
    clock: dict[str, Any]
    predicted_payment_date: str | None
    avg_days_late: float | None
    behavior_observations: int


class RadarOut(BaseModel):
    items: list[RadarItem]
    totals: dict[str, int]
    ca_note: str


@router.get("/receivables/radar", response_model=RadarOut)
async def radar(auth: Auth) -> RadarOut:
    now = datetime.now(UTC)
    items: list[RadarItem] = []
    total_overdue = 0
    total_interest = 0

    async with session_scope() as session:
        repo = BooksRepo(session)
        invoices = await repo.open_invoices(auth.tenant_id)
        parties = {c.id: c.name for c in await repo.counterparties(auth.tenant_id)}
        clocks = {
            c.invoice_id: c
            for c in await session.scalars(
                select(StatutoryClock).where(StatutoryClock.tenant_id == auth.tenant_id)
            )
        }

        for inv in invoices:
            acceptance = inv.acceptance_date or inv.issue_date
            snap = clock_snapshot(
                acceptance_date=acceptance, amount_paise=inv.amount_paise, now=now
            )

            clock = clocks.get(inv.id)
            if clock is None:
                clock = StatutoryClock(
                    id=uuid7(),
                    tenant_id=auth.tenant_id,
                    invoice_id=inv.id,
                    acceptance_date=acceptance,
                    statutory_due_date=datetime.fromisoformat(snap["statutory_due_date"]),
                    annual_rate_bps=snap["annual_rate_bps"],
                )
                session.add(clock)
            clock.overdue_days = snap["overdue_days"]
            clock.accrued_interest_paise = snap["accrued_interest_paise"]
            clock.escalation_level = snap["escalation_level"]

            memories = await memoryclient.retrieve_units(
                tenant_id=auth.tenant_id,
                scope_key=f"client:{inv.counterparty_id}",
                query="payment behavior: how late does this client pay?",
            )
            lates = parse_late_days([m.get("content", "") for m in memories.values()])
            avg_late = round(sum(lates) / len(lates), 1) if lates else None
            predicted = (
                (inv.due_date + timedelta(days=avg_late)).date().isoformat()
                if avg_late is not None
                else None
            )

            if snap["overdue_days"] > 0:
                total_overdue += inv.amount_paise
                total_interest += snap["accrued_interest_paise"]

            items.append(
                RadarItem(
                    invoice_id=inv.id,
                    invoice_number=inv.number,
                    client=parties.get(inv.counterparty_id, "?"),
                    amount_paise=inv.amount_paise,
                    clock=snap,
                    predicted_payment_date=predicted,
                    avg_days_late=avg_late,
                    behavior_observations=len(lates),
                )
            )

    items.sort(key=lambda i: i.clock["overdue_days"], reverse=True)
    return RadarOut(
        items=items,
        totals={"overdue_paise": total_overdue, "accrued_interest_paise": total_interest},
        ca_note=CA_NOTE,
    )
