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

from fastapi import APIRouter, HTTPException, status
from findesk_shared import parse_late_days, uuid7
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import memoryclient
from app.auth.deps import Auth
from app.db import session_scope
from app.db.books_repo import BooksRepo
from app.db.models import Invoice, PaymentPromise
from app.services.audit import write_audit
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
    open_promise_date: str | None = None
    promises_kept: int = 0
    promises_broken: int = 0


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

        # F3: one bulk pull of PTP state for every open invoice on the radar
        promises_by_invoice: dict[str, dict[str, Any]] = {}
        for p in await session.scalars(
            select(PaymentPromise).where(PaymentPromise.tenant_id == auth.tenant_id)
        ):
            slot = promises_by_invoice.setdefault(p.invoice_id, {"kept": 0, "broken": 0})
            if p.status == "open":
                # earliest open promise is the operative one
                current = slot.get("open")
                candidate = p.promised_date.date().isoformat()
                slot["open"] = min(current, candidate) if current else candidate
            elif p.status in {"kept", "broken"}:
                slot[p.status] += 1

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

        promise = promises_by_invoice.get(inv.id, {})
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
                open_promise_date=promise.get("open"),
                promises_kept=promise.get("kept", 0),
                promises_broken=promise.get("broken", 0),
            )
        )

    items.sort(key=lambda i: i.clock["overdue_days"], reverse=True)
    return RadarOut(
        items=items,
        totals={"overdue_paise": total_overdue, "accrued_interest_paise": total_interest},
        ca_note=CA_NOTE,
    )


class PromiseCreate(BaseModel):
    promised_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount_paise: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=200)


REQUESTER_ROLES = {"owner", "accountant", "ca"}


@router.post("/receivables/{invoice_id}/promise", status_code=status.HTTP_201_CREATED)
async def log_promise(invoice_id: str, body: PromiseCreate, auth: Auth) -> dict[str, Any]:
    """Capture a client's promise-to-pay. Settlement classifies it kept/broken
    when recon marks the invoice paid — never by hand."""
    if auth.role not in REQUESTER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot log promises")
    from datetime import UTC, datetime

    async with session_scope() as session:
        inv = await session.scalar(
            select(Invoice).where(
                Invoice.id == invoice_id, Invoice.tenant_id == auth.tenant_id
            )
        )
        if inv is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
        if inv.status != "open":
            raise HTTPException(status.HTTP_409_CONFLICT, f"invoice already {inv.status}")
        promise = PaymentPromise(
            id=uuid7(),
            tenant_id=auth.tenant_id,
            invoice_id=inv.id,
            promised_date=datetime.fromisoformat(body.promised_date).replace(tzinfo=UTC),
            amount_paise=body.amount_paise,
            status="open",
            source="manual",
            note=body.note,
        )
        session.add(promise)
        await write_audit(
            session,
            tenant_id=auth.tenant_id,
            actor={"kind": "user", "id": auth.user_id},
            action="promise.logged",
            entity_ref=f"invoice:{inv.id}",
            payload={
                "promise_id": promise.id,
                "invoice_number": inv.number,
                "promised_date": body.promised_date,
                "amount_paise": body.amount_paise,
            },
        )
        return {"ok": True, "promise_id": promise.id}
