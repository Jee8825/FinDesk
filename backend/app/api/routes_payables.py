"""Buyer-side payables compliance — §15 clock + 43B(h) exposure per MSE bill.

The mirror of the receivables radar: same statutory engine, opposite
direction. Router stays thin; math lives in services/payables.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.deps import Auth
from app.config import get_settings
from app.db import session_scope
from app.db.books_repo import BooksRepo
from app.services.payables import CA_NOTE, MSE_STATUSES, compliance_row, totals

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


@router.get("/payables/compliance", response_model=PayablesOut)
async def payables_compliance(auth: Auth) -> PayablesOut:
    now = datetime.now(UTC)
    async with session_scope() as session:
        repo = BooksRepo(session)
        parties = {c.id: c for c in await repo.counterparties(auth.tenant_id)}
        bills = await repo.open_bills(auth.tenant_id)

    items: list[PayableItem] = []
    rows: list[dict[str, Any]] = []
    amounts: list[int] = []
    non_mse = 0
    for bill in bills:
        party = parties.get(bill.counterparty_id)
        status = (party.msme_status or "").lower() if party else ""
        if status not in MSE_STATUSES:
            non_mse += 1  # outside §15/43B(h); counted so the page can say so
            continue
        row = compliance_row(
            amount_paise=bill.outstanding_paise,  # §16/43B(h) run on the unpaid portion
            acceptance_date=bill.acceptance_date or bill.issue_date,
            now=now,
            bank_rate_bps=get_settings().statutory_bank_rate_bps,
        )
        rows.append(row)
        amounts.append(bill.outstanding_paise)
        items.append(
            PayableItem(
                bill_id=bill.id,
                bill_number=bill.number,
                vendor=party.name if party else "unknown",
                msme_status=status,
                amount_paise=bill.amount_paise,
                outstanding_paise=bill.outstanding_paise,
                clock=row,
            )
        )

    # most urgent first: breached by overdue days, then closing windows
    items.sort(key=lambda i: (-i.clock["overdue_days"], i.clock["days_left"]))
    return PayablesOut(
        items=items, totals=totals(rows, amounts), non_mse_open_count=non_mse, ca_note=CA_NOTE
    )
