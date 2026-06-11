"""Shared statutory-clock recompute — one writer for radar and enforcer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from findesk_shared import uuid7
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.books_repo import BooksRepo
from app.db.models import Invoice, StatutoryClock
from app.services.statutory import clock_snapshot


async def recompute_clocks(
    session: AsyncSession, tenant_id: str
) -> list[tuple[Invoice, StatutoryClock, dict[str, Any]]]:
    """Upsert a clock per open invoice; return (invoice, clock, snapshot) rows."""
    now = datetime.now(UTC)
    repo = BooksRepo(session)
    invoices = await repo.open_invoices(tenant_id)
    clocks = {
        c.invoice_id: c
        for c in await session.scalars(
            select(StatutoryClock).where(StatutoryClock.tenant_id == tenant_id)
        )
    }
    out = []
    for inv in invoices:
        acceptance = inv.acceptance_date or inv.issue_date
        snap = clock_snapshot(acceptance_date=acceptance, amount_paise=inv.amount_paise, now=now)
        clock = clocks.get(inv.id)
        if clock is None:
            clock = StatutoryClock(
                id=uuid7(),
                tenant_id=tenant_id,
                invoice_id=inv.id,
                acceptance_date=acceptance,
                statutory_due_date=datetime.fromisoformat(snap["statutory_due_date"]),
                annual_rate_bps=snap["annual_rate_bps"],
            )
            session.add(clock)
        clock.overdue_days = snap["overdue_days"]
        clock.accrued_interest_paise = snap["accrued_interest_paise"]
        clock.escalation_level = snap["escalation_level"]
        out.append((inv, clock, snap))
    return out
