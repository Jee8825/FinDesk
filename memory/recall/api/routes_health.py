"""Health and aggregate-stats endpoints (also consumed by the dashboard)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from recall.db import get_redis, session_scope
from recall.db.models import ConflictLog, MemoryUnit, PrefetchEvent

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/stats")
async def stats(tenant_id: str = "default") -> dict:
    """Tier counts, status breakdown, conflict total, prefetch hit-rate.

    Powers the dashboard's summary panels.
    """
    async with session_scope() as s:
        tier_rows = (
            await s.execute(
                select(MemoryUnit.tier, MemoryUnit.status, func.count())
                .where(MemoryUnit.tenant_id == tenant_id)
                .group_by(MemoryUnit.tier, MemoryUnit.status)
            )
        ).all()
        conflicts = (
            await s.execute(
                select(func.count()).select_from(ConflictLog).where(
                    ConflictLog.tenant_id == tenant_id
                )
            )
        ).scalar_one()
        pf_total = (
            await s.execute(select(func.count()).select_from(PrefetchEvent))
        ).scalar_one()
        pf_hits = (
            await s.execute(
                select(func.count()).select_from(PrefetchEvent).where(PrefetchEvent.consumed.is_(True))
            )
        ).scalar_one()

    by_tier: dict[str, dict[str, int]] = {}
    for tier, status, count in tier_rows:
        by_tier.setdefault(tier, {})[status] = count

    return {
        "tenant_id": tenant_id,
        "memory_by_tier": by_tier,
        "conflicts_total": conflicts,
        "prefetch": {
            "total": pf_total,
            "hits": pf_hits,
            "hit_rate": (pf_hits / pf_total) if pf_total else 0.0,
        },
        "redis": "connected" if await _redis_ok() else "unavailable",
    }


async def _redis_ok() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:  # noqa: BLE001
        return False
