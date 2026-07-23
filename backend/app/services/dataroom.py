"""B5 credit-ready data room — provenance converted into credit-worthiness.

Two deterministic artifacts a lender can underwrite against:

1. **Audit-chain verification** — re-walks the tenant's hash chain
   (row_hash = sha256(prev_hash ‖ canonical_payload)) and reports the first
   break, if any. A verified chain means no figure was edited after the fact.
2. **FinDesk Score** — 0–100, a weighted composite of measurable book
   hygiene. Components and weights are published (the score is an argument,
   not an oracle); each component carries its raw inputs so a lender's
   analyst can recompute everything.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Anomaly,
    BankTransaction,
    Conflict,
    Forecast,
    Invoice,
    Match,
)
from app.services.audit import verify_chain

WEIGHTS = {
    "reconciliation": 25,
    "categorization": 15,
    "audit_integrity": 20,
    "receivables_discipline": 15,
    "conflict_hygiene": 10,
    "forecast_freshness": 15,
}


async def verify_audit_chain(session: AsyncSession, tenant_id: str) -> dict[str, Any]:
    """Adapter over the canonical walker in services/audit.py.

    One recomputation algorithm in the codebase (lap-3 dedup — two copies had
    already drifted in shape); this keeps the data room's published key names
    stable for consumers.
    """
    raw = await verify_chain(session, tenant_id)
    broken = raw.get("broken_at") or {}
    return {
        "ok": raw["valid"],
        "rows": raw["entries"],
        "head_hash": raw["head_hash"],
        "first_break_index": broken.get("index"),
        "first_break_id": broken.get("id"),
    }


def compute_score(components: dict[str, float]) -> dict[str, Any]:
    """Weighted 0–100 from component ratios (each 0.0–1.0)."""
    detail = {}
    total = 0.0
    for name, weight in WEIGHTS.items():
        ratio = max(0.0, min(1.0, components.get(name, 0.0)))
        points = ratio * weight
        total += points
        detail[name] = {"ratio": round(ratio, 3), "weight": weight, "points": round(points, 1)}
    return {"score": round(total), "components": detail}


async def build_dataroom(session: AsyncSession, tenant_id: str) -> dict[str, Any]:
    now = datetime.now(UTC)

    txn_total = await session.scalar(
        select(func.count()).select_from(BankTransaction).where(
            BankTransaction.tenant_id == tenant_id
        )
    )
    txn_matched = await session.scalar(
        select(func.count()).select_from(BankTransaction).where(
            BankTransaction.tenant_id == tenant_id, BankTransaction.match_status == "matched"
        )
    )
    debit_total = await session.scalar(
        select(func.count()).select_from(BankTransaction).where(
            BankTransaction.tenant_id == tenant_id, BankTransaction.direction == "dr"
        )
    )
    debit_categorized = await session.scalar(
        select(func.count()).select_from(BankTransaction).where(
            BankTransaction.tenant_id == tenant_id,
            BankTransaction.direction == "dr",
            BankTransaction.category_code.is_not(None),
        )
    )
    matches_committed = await session.scalar(
        select(func.count()).select_from(Match).where(
            Match.tenant_id == tenant_id, Match.status == "committed"
        )
    )
    tds_matches = await session.scalar(
        select(func.count()).select_from(Match).where(
            Match.tenant_id == tenant_id, Match.kind == "tds_adjusted",
            Match.status == "committed",
        )
    )
    invoices_open = list(
        await session.scalars(
            select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.status == "open")
        )
    )
    overdue_paise = sum(i.amount_paise for i in invoices_open if i.due_date < now)
    open_total_paise = sum(i.amount_paise for i in invoices_open)
    conflicts_open = await session.scalar(
        select(func.count()).select_from(Conflict).where(
            Conflict.tenant_id == tenant_id, Conflict.status == "open"
        )
    )
    conflicts_resolved = await session.scalar(
        select(func.count()).select_from(Conflict).where(
            Conflict.tenant_id == tenant_id, Conflict.status == "resolved"
        )
    )
    anomalies_open = await session.scalar(
        select(func.count()).select_from(Anomaly).where(
            Anomaly.tenant_id == tenant_id, Anomaly.status == "open"
        )
    )
    latest_forecast = await session.scalar(
        select(Forecast)
        .where(Forecast.tenant_id == tenant_id)
        .order_by(Forecast.created_at.desc())
        .limit(1)
    )
    chain = await verify_audit_chain(session, tenant_id)

    forecast_age_days = (
        (now - latest_forecast.created_at).days if latest_forecast else None
    )
    score = compute_score(
        {
            "reconciliation": (txn_matched / txn_total) if txn_total else 0.0,
            "categorization": (debit_categorized / debit_total) if debit_total else 0.0,
            "audit_integrity": 1.0 if chain["ok"] else 0.0,
            "receivables_discipline": (
                1.0 - (overdue_paise / open_total_paise) if open_total_paise else 1.0
            ),
            "conflict_hygiene": (
                conflicts_resolved / (conflicts_open + conflicts_resolved)
                if (conflicts_open + conflicts_resolved)
                else 1.0
            ),
            "forecast_freshness": (
                max(0.0, 1.0 - (forecast_age_days / 14)) if forecast_age_days is not None else 0.0
            ),
        }
    )

    return {
        "generated_at": now.isoformat(),
        "findesk_score": score,
        "audit_chain": chain,
        "evidence": {
            "bank_transactions": int(txn_total or 0),
            "matched_transactions": int(txn_matched or 0),
            "committed_matches": int(matches_committed or 0),
            "tds_adjusted_matches": int(tds_matches or 0),
            "debits_categorized": f"{int(debit_categorized or 0)}/{int(debit_total or 0)}",
            "open_receivables_paise": open_total_paise,
            "overdue_receivables_paise": overdue_paise,
            "conflicts_resolved": int(conflicts_resolved or 0),
            "conflicts_open": int(conflicts_open or 0),
            "anomalies_open": int(anomalies_open or 0),
            "audit_events": chain["rows"],
            "latest_forecast_at": (
                latest_forecast.created_at.isoformat() if latest_forecast else None
            ),
        },
        "methodology_note": (
            "Score components, weights and raw inputs are published so any "
            "analyst can recompute them; the audit chain is independently "
            "verifiable hash-by-hash. Every number traces to a statement line "
            "via the Why API."
        ),
    }
