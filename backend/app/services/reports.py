"""A8 month-end report pack — every number carries the refs to answer "Why?".

Pure composition over the app DB (no LLM): cash flow by category, match
statistics, AR aging, anomaly recoverables, and a deterministic narrative.
Each line item includes ``why`` refs (entity kind + id) that the UI resolves
through GET /why/{kind}/{id} — explainability is the product, not a log.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime
from typing import Any

from findesk_shared import format_inr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Anomaly,
    BankTransaction,
    ChartAccount,
    Counterparty,
    Invoice,
    Match,
)

AGING_BUCKETS = ((0, 30), (31, 60), (61, None))


def period_bounds(period: str) -> tuple[datetime, datetime]:
    """'YYYY-MM' → [start, end) datetimes in UTC. Raises ValueError if bad."""
    year, month = (int(x) for x in period.split("-", 1))
    if not 1 <= month <= 12:
        raise ValueError(f"bad month in period {period!r}")
    start = datetime(year, month, 1, tzinfo=UTC)
    last_day = monthrange(year, month)[1]
    end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=UTC)
    )
    assert last_day  # monthrange can't fail here; keeps mypy honest
    return start, end


def aging_bucket(days_overdue: int) -> str:
    for low, high in AGING_BUCKETS:
        if high is None or days_overdue <= high:
            if days_overdue >= low:
                return f"{low}–{high}" if high else f"{low}+"
    return "0–30"


async def month_end_report(session: AsyncSession, tenant_id: str, period: str) -> dict[str, Any]:
    start, end = period_bounds(period)
    now = datetime.now(UTC)

    txns = list(
        await session.scalars(
            select(BankTransaction).where(
                BankTransaction.tenant_id == tenant_id,
                BankTransaction.value_date >= start,
                BankTransaction.value_date < end,
            )
        )
    )
    chart = {
        c.code: c.name
        for c in await session.scalars(
            select(ChartAccount).where(ChartAccount.tenant_id == tenant_id)
        )
    }
    # matches belong to the period of their *transaction*, not of the run that
    # posted them (a June run reconciling April's statement is April activity)
    txn_ids = [t.id for t in txns]
    matches = (
        list(
            await session.scalars(
                select(Match).where(
                    Match.tenant_id == tenant_id,
                    Match.status == "committed",
                    Match.bank_transaction_id.in_(txn_ids),
                )
            )
        )
        if txn_ids
        else []
    )
    open_invoices = list(
        await session.scalars(
            select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.status == "open")
        )
    )
    parties = {
        c.id: c.name
        for c in await session.scalars(
            select(Counterparty).where(Counterparty.tenant_id == tenant_id)
        )
    }
    open_anomalies = list(
        await session.scalars(
            select(Anomaly).where(Anomaly.tenant_id == tenant_id, Anomaly.status == "open")
        )
    )

    # ---- cash flow ---------------------------------------------------------
    inflow = sum(t.amount_paise for t in txns if t.direction == "cr")
    outflow = sum(t.amount_paise for t in txns if t.direction == "dr")
    by_category: dict[str, dict[str, Any]] = {}
    for t in txns:
        if t.direction != "dr":
            continue
        code = t.category_code or "uncategorized"
        entry = by_category.setdefault(
            code,
            {
                "category_code": code,
                "category_name": chart.get(code, "Uncategorized"),
                "amount_paise": 0,
                "count": 0,
                "why": [],
            },
        )
        entry["amount_paise"] += t.amount_paise
        entry["count"] += 1
        entry["why"].append({"kind": "bank_transaction", "id": t.id})

    # ---- reconciliation ----------------------------------------------------
    matched_amount = sum(
        next((t.amount_paise for t in txns if t.id == m.bank_transaction_id), 0)
        for m in matches
    )
    tds_matches = [m for m in matches if m.kind == "tds_adjusted"]
    unmatched_in_period = [t for t in txns if t.match_status == "unmatched"]

    # ---- receivables aging --------------------------------------------------
    aging: dict[str, dict[str, Any]] = {}
    overdue_total = 0
    for inv in open_invoices:
        days = (now - inv.due_date).days
        if days < 0:
            continue
        overdue_total += inv.amount_paise
        bucket = aging.setdefault(
            aging_bucket(days), {"bucket": aging_bucket(days), "amount_paise": 0, "items": []}
        )
        bucket["amount_paise"] += inv.amount_paise
        bucket["items"].append(
            {
                "invoice_number": inv.number,
                "client": parties.get(inv.counterparty_id, "?"),
                "amount_paise": inv.amount_paise,
                "days_overdue": days,
                "why": [{"kind": "invoice", "id": inv.id}],
            }
        )

    recoverable = sum(a.recoverable_paise or 0 for a in open_anomalies)

    # ---- deterministic narrative --------------------------------------------
    matched_pct = round(100 * len(matches) / len(txns)) if txns else 0
    narrative = [
        f"In {period}, {format_inr(inflow)} came in and {format_inr(outflow)} went out "
        f"across {len(txns)} bank transactions.",
        f"The agent matched and posted {len(matches)} of them ({matched_pct}%)"
        + (f", including {len(tds_matches)} TDS-adjusted settlements" if tds_matches else "")
        + f"; {len(unmatched_in_period)} remain for review.",
    ]
    if overdue_total:
        narrative.append(
            f"{format_inr(overdue_total)} of receivables is past due — "
            "the collections agent has drafts ready for approval."
        )
    if recoverable:
        narrative.append(
            f"Open anomalies flag {format_inr(recoverable)} as potentially recoverable."
        )

    return {
        "period": period,
        "generated_at": now.isoformat(),
        "cash": {
            "inflow_paise": inflow,
            "outflow_paise": outflow,
            "net_paise": inflow - outflow,
            "by_category": sorted(
                by_category.values(), key=lambda e: e["amount_paise"], reverse=True
            ),
        },
        "reconciliation": {
            "transactions": len(txns),
            "matched": len(matches),
            "matched_amount_paise": matched_amount,
            "tds_matches": len(tds_matches),
            "unmatched": len(unmatched_in_period),
            "why": [{"kind": "match", "id": m.id} for m in matches],
        },
        "receivables": {
            "overdue_total_paise": overdue_total,
            "aging": sorted(aging.values(), key=lambda b: b["bucket"]),
        },
        "anomalies": {
            "open": len(open_anomalies),
            "recoverable_paise": recoverable,
            "why": [{"kind": "anomaly", "id": a.id} for a in open_anomalies],
        },
        "narrative": narrative,
    }
