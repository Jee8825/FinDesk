"""LeakRadar read model + the usage-confirmation loop.

The scan (agents/subscription_scan) produces every number; this layer reads them
back and owns the one thing a scan cannot derive — the human's answer about
whether a subscription is still used. That answer is written to Recall as a
decaying belief, so it is re-asked when it goes stale rather than trusted forever.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Subscription, Tenant
from app.services.audit import write_audit

CA_NOTE = (
    "Cadence, price changes and recoverable amounts are computed from your own "
    "bank debits. Whether a service is still used is your call, not an inference "
    "— confirm each one before cancelling."
)

USAGE_VALUES = ("in_use", "unused")


async def list_leaks(session: AsyncSession, *, tenant_id: str) -> list[Subscription]:
    """Highest recoverable money first, then score. Mirrors scoring.rank()."""
    rows = list(
        await session.scalars(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        )
    )
    status_order = {"active": 0, "stopped": 1}
    rows.sort(
        key=lambda s: (
            status_order.get(s.status, 2),
            -s.recoverable_paise_per_year,
            -s.leak_score,
            -s.run_rate_paise,
        )
    )
    return rows


def totals(rows: list[Subscription]) -> dict[str, Any]:
    """Headline figures plus category-wise annualized cost. Pure.

    The category breakdown deliberately EXCLUDES commitments. Payroll and rent
    are an order of magnitude larger than any subscription, so leaving them in
    flattens every other bar to a sliver and the chart stops answering the
    question it exists for. They are reported as one separate figure instead, so
    nothing is hidden.
    """
    active = [r for r in rows if r.status == "active"]
    by_category: dict[str, int] = {}
    commitments = 0
    for r in active:
        if r.drift_kind == "excluded":
            commitments += r.run_rate_paise
            continue
        key = r.category_code or "uncategorized"
        by_category[key] = by_category.get(key, 0) + r.run_rate_paise
    return {
        "subscriptions": len(active),
        "stopped": len(rows) - len(active),
        "committed_paise_per_year": sum(r.run_rate_paise for r in active),
        "subscription_paise_per_year": sum(by_category.values()),
        "commitments_paise_per_year": commitments,
        "recoverable_paise_per_year": sum(r.recoverable_paise_per_year for r in active),
        "drift_paise_per_year": sum(r.drift_paise_per_year for r in active),
        "leaking_count": sum(1 for r in active if r.recoverable_paise_per_year > 0),
        "unreviewed_count": sum(1 for r in active if r.usage is None),
        "by_category_paise": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
    }


async def mode_for(session: AsyncSession, tenant_id: str) -> str:
    tenant = await session.get(Tenant, tenant_id)
    return (tenant.leak_mode if tenant else None) or "business"


def usage_memory_content(vendor_label: str, usage: str) -> str:
    """The sentence stored in Recall.

    Phrased so `recall_usage` in the graph can read it back, and so a human
    reading the memory log sees a claim rather than a code.
    """
    if usage == "unused":
        return f"The user no longer uses the subscription '{vendor_label}'."
    return f"The user still uses the subscription '{vendor_label}'."


async def set_usage(
    session: AsyncSession,
    *,
    tenant_id: str,
    subscription_id: str,
    usage: str,
    actor_id: str,
) -> dict[str, Any]:
    """Record the human's answer. Does NOT rescore.

    Rescoring is the scan's job, and doing it here would duplicate the money
    arithmetic in a second place — the next run picks the answer up from memory.
    The response says so explicitly rather than implying the table is already
    updated.
    """
    if usage not in USAGE_VALUES:
        return {"ok": False, "reason": f"usage must be one of {USAGE_VALUES}"}

    row = await session.scalar(
        select(Subscription).where(
            Subscription.id == subscription_id, Subscription.tenant_id == tenant_id
        )
    )
    if row is None:
        return {"ok": False, "reason": "not found"}

    row.usage = usage
    row.usage_confirmed_at = datetime.now(UTC)
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor={"kind": "user", "id": actor_id},
        action="leak.usage_confirmed",
        entity_ref=f"subscription:{row.id}",
        payload={
            "vendor_slug": row.vendor_slug,
            "vendor_label": row.vendor_label,
            "usage": usage,
            "run_rate_paise": row.run_rate_paise,
        },
    )
    return {
        "ok": True,
        "usage": usage,
        "vendor_slug": row.vendor_slug,
        "memory_content": usage_memory_content(row.vendor_label, usage),
        "rescore_required": True,
    }
