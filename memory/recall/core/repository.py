"""Data-access layer for memory units (all Postgres SQL lives here).

Keeping queries in one module means the engine modules (ingestion, retrieval,
decay sweeps, conflict) stay free of SQLAlchemy details and are easy to test.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from recall.core.types import Scope, Tier
from recall.db.models import MemoryUnit


def _now() -> datetime:
    return datetime.now(UTC)


async def insert_memory(
    session: AsyncSession,
    *,
    user_id: str,
    tenant_id: str,
    tier: Tier,
    content: str,
    embedding: list[float],
    decay_lambda: float,
    confidence: float,
    scope: Scope,
    team_id: str | None,
    cluster: str | None,
    source_session_id: str | None,
) -> MemoryUnit:
    unit = MemoryUnit(
        user_id=user_id,
        tenant_id=tenant_id,
        tier=tier,
        content=content,
        embedding=embedding,
        decay_lambda=decay_lambda,
        confidence=confidence,
        scope=scope,
        team_id=team_id,
        cluster=cluster,
        source_session_id=source_session_id,
        strength=1.0,
        strength_updated_at=_now(),
    )
    session.add(unit)
    await session.flush()
    return unit


async def get_memory(session: AsyncSession, memory_id: uuid.UUID) -> MemoryUnit | None:
    return await session.get(MemoryUnit, memory_id)


async def search_similar(
    session: AsyncSession,
    *,
    embedding: list[float],
    user_id: str,
    tenant_id: str,
    limit: int,
    scope: Scope | None = None,
    team_id: str | None = None,
    tiers: tuple[Tier, ...] | None = None,
    include_tombstoned: bool = False,
) -> list[tuple[MemoryUnit, float]]:
    """Vector search returning ``(unit, cosine_distance)`` pairs, nearest first.

    Scope visibility rules are applied here (private/team/global/user-owned).
    """
    distance = MemoryUnit.embedding.cosine_distance(embedding).label("distance")
    stmt = select(MemoryUnit, distance).where(MemoryUnit.tenant_id == tenant_id)

    if not include_tombstoned:
        stmt = stmt.where(MemoryUnit.status != "tombstoned")
    if tiers:
        stmt = stmt.where(MemoryUnit.tier.in_(tiers))

    stmt = stmt.where(_visibility_clause(user_id, scope, team_id))
    stmt = stmt.order_by(distance).limit(limit)

    rows = (await session.execute(stmt)).all()
    return [(row[0], float(row[1])) for row in rows]


def _visibility_clause(user_id: str, scope: Scope | None, team_id: str | None):
    """Build the WHERE clause enforcing cross-agent scope visibility.

    Default (no explicit scope): the caller sees their own private + user-owned
    memories, anything global, and team memories for their team.
    """
    from sqlalchemy import and_, or_

    if scope == "team" and team_id:
        return and_(MemoryUnit.scope == "team", MemoryUnit.team_id == team_id)
    if scope == "global":
        return MemoryUnit.scope == "global"
    if scope == "private":
        return and_(MemoryUnit.scope.in_(["private", "user-owned"]), MemoryUnit.user_id == user_id)

    clauses = [
        and_(MemoryUnit.scope.in_(["private", "user-owned"]), MemoryUnit.user_id == user_id),
        MemoryUnit.scope == "global",
    ]
    if team_id:
        clauses.append(and_(MemoryUnit.scope == "team", MemoryUnit.team_id == team_id))
    return or_(*clauses)


async def list_semantic_for_user(
    session: AsyncSession, *, user_id: str, tenant_id: str
) -> list[MemoryUnit]:
    """All active semantic units for a user (used by conflict detection)."""
    stmt = select(MemoryUnit).where(
        MemoryUnit.tenant_id == tenant_id,
        MemoryUnit.user_id == user_id,
        MemoryUnit.tier == "semantic",
        MemoryUnit.status == "active",
    )
    return list((await session.execute(stmt)).scalars().all())


async def apply_reinforcement(
    session: AsyncSession, memory_id: uuid.UUID, new_strength: float
) -> None:
    """Persist a reinforced strength and refresh the decay clock + retrieval stats."""
    await session.execute(
        update(MemoryUnit)
        .where(MemoryUnit.id == memory_id)
        .values(
            strength=new_strength,
            strength_updated_at=_now(),
            last_retrieved_at=_now(),
            retrieval_count=MemoryUnit.retrieval_count + 1,
        )
    )


async def set_status(session: AsyncSession, memory_id: uuid.UUID, status: str) -> None:
    await session.execute(
        update(MemoryUnit).where(MemoryUnit.id == memory_id).values(status=status)
    )


async def update_scope(
    session: AsyncSession, memory_id: uuid.UUID, scope: Scope, team_id: str | None
) -> None:
    await session.execute(
        update(MemoryUnit)
        .where(MemoryUnit.id == memory_id)
        .values(scope=scope, team_id=team_id)
    )


async def list_user_owned(
    session: AsyncSession, *, user_id: str, tenant_id: str
) -> list[MemoryUnit]:
    stmt = select(MemoryUnit).where(
        MemoryUnit.tenant_id == tenant_id,
        MemoryUnit.user_id == user_id,
        MemoryUnit.scope == "user-owned",
    )
    return list((await session.execute(stmt)).scalars().all())


async def delete_memory(session: AsyncSession, memory_id: uuid.UUID) -> None:
    unit = await session.get(MemoryUnit, memory_id)
    if unit is not None:
        await session.delete(unit)


# --------------------------- consolidation helpers ---------------------------

async def list_active_by_user(
    session: AsyncSession,
    *,
    user_id: str,
    tenant_id: str,
    tier: Tier | None = None,
) -> list[MemoryUnit]:
    stmt = select(MemoryUnit).where(
        MemoryUnit.tenant_id == tenant_id,
        MemoryUnit.user_id == user_id,
        MemoryUnit.status == "active",
    )
    if tier:
        stmt = stmt.where(MemoryUnit.tier == tier)
    return list((await session.execute(stmt)).scalars().all())


async def update_fields(session: AsyncSession, memory_id: uuid.UUID, **values) -> None:
    await session.execute(
        update(MemoryUnit).where(MemoryUnit.id == memory_id).values(**values)
    )


async def distinct_clusters(
    session: AsyncSession, *, user_id: str, tenant_id: str
) -> list[str]:
    rows = (
        await session.execute(
            select(MemoryUnit.cluster)
            .where(
                MemoryUnit.tenant_id == tenant_id,
                MemoryUnit.user_id == user_id,
                MemoryUnit.status == "active",
                MemoryUnit.cluster.is_not(None),
            )
            .distinct()
        )
    ).scalars().all()
    return [c for c in rows if c]


async def list_by_cluster(
    session: AsyncSession, *, user_id: str, tenant_id: str, cluster: str, limit: int = 50
) -> list[MemoryUnit]:
    stmt = (
        select(MemoryUnit)
        .where(
            MemoryUnit.tenant_id == tenant_id,
            MemoryUnit.user_id == user_id,
            MemoryUnit.status != "tombstoned",
            MemoryUnit.cluster == cluster,
        )
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def hard_delete_tombstoned_before(
    session: AsyncSession, *, tenant_id: str, cutoff: datetime
) -> int:
    """Permanently remove tombstoned units last updated before ``cutoff``.

    Returns the number of rows deleted. This is the compaction step that keeps
    soft-deleted tombstones from growing unboundedly.
    """
    rows = (
        await session.execute(
            select(MemoryUnit).where(
                MemoryUnit.tenant_id == tenant_id,
                MemoryUnit.status == "tombstoned",
                MemoryUnit.updated_at < cutoff,
            )
        )
    ).scalars().all()
    for r in rows:
        await session.delete(r)
    return len(rows)
