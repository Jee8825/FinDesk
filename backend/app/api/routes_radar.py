"""B2 receivables radar — statutory clocks + B1 payment predictions.

Reading the radar recomputes and persists every open invoice's clock (the
enforcer graph will consume rung *transitions* from these rows). Predictions
come from remembered payment behavior; statutory figures are engine-computed
and ship with explicit review-with-your-CA framing.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from fastapi import APIRouter
from findesk_shared import parse_late_days
from pydantic import BaseModel

from app import memoryclient
from app.auth.deps import Auth
from app.db import session_scope
from app.db.books_repo import BooksRepo
from app.services.clocks import recompute_clocks

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
    items: list[RadarItem] = []
    total_overdue = 0
    total_interest = 0

    async with session_scope() as session:
        repo = BooksRepo(session)
        parties = {c.id: c.name for c in await repo.counterparties(auth.tenant_id)}
        rows = await recompute_clocks(session, auth.tenant_id)

    # one memory retrieval per *client* (not per invoice), all concurrent —
    # the memoryclient semaphore bounds the fan-out
    client_ids = sorted({inv.counterparty_id for inv, _, _ in rows})
    recalled = dict(
        zip(
            client_ids,
            await asyncio.gather(
                *(
                    memoryclient.retrieve_units(
                        tenant_id=auth.tenant_id,
                        scope_key=f"client:{cid}",
                        query="payment behavior: how late does this client pay?",
                    )
                    for cid in client_ids
                )
            ),
            strict=True,
        )
    )

    for inv, _clock, snap in rows:
        memories = recalled.get(inv.counterparty_id, {})
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
