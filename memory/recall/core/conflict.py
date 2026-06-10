"""Conflict detection + resolution.

On ingestion of a new semantic memory, Recall checks it against existing
semantic memories for the same user. Two units that are *semantically close* but
*factually opposite* raise a conflict, which the heavy LLM resolves using
recency, confidence, and context. The resolution is one of:

* auto_resolved — one belief supersedes the other
* merged        — both fold into a nuanced composite belief
* flagged       — genuinely ambiguous; ask the user next session

Every resolution is logged permanently (``conflict_log``) and recorded in the
provenance graph, so the *evolution* of a belief is preserved, not just its
current state.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from recall.core import decay, prompts
from recall.core.types import Resolution
from recall.db.models import ConflictLog, MemoryUnit
from recall.logging import get_logger
from recall.providers import LLMProvider, ProviderError

log = get_logger(__name__)


class ResolutionOutput(BaseModel):
    resolution: Resolution
    resolved_belief: str
    rationale: str


def cosine_distance(a: list[float], b: list[float]) -> float:
    """Cosine distance (1 - cosine similarity) between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)


def find_nearest(
    new_embedding: list[float],
    candidates: list[MemoryUnit],
    threshold: float,
) -> tuple[MemoryUnit, float] | None:
    """Return the closest existing unit within ``threshold`` distance, if any.

    "Within threshold" means the two facts are about the same thing; whether they
    actually contradict is decided by the LLM resolver.
    """
    best: tuple[MemoryUnit, float] | None = None
    for unit in candidates:
        if unit.embedding is None:
            continue
        dist = cosine_distance(new_embedding, list(unit.embedding))
        if dist <= threshold and (best is None or dist < best[1]):
            best = (unit, dist)
    return best


async def resolve(
    llm: LLMProvider,
    *,
    existing: MemoryUnit,
    new_content: str,
    new_confidence: float,
    now: datetime | None = None,
) -> ResolutionOutput:
    """Ask the heavy LLM to reconcile a conflict between two beliefs."""
    now = now or datetime.now(UTC)
    prompt = prompts.render(
        "conflict_resolution",
        existing_content=existing.content,
        existing_confidence=round(existing.confidence, 2),
        existing_age_days=round(decay.elapsed_days(existing.created_at, now), 1),
        new_content=new_content,
        new_confidence=round(new_confidence, 2),
    )
    try:
        return await llm.complete_structured(prompt, ResolutionOutput, role="heavy")
    except ProviderError as exc:
        # Fallback: last-write-wins-style auto-resolution to the newer belief.
        log.warning("conflict.resolve_failed", error=str(exc))
        return ResolutionOutput(
            resolution="auto_resolved",
            resolved_belief=new_content,
            rationale="resolver unavailable; defaulted to most recent belief",
        )


async def log_conflict(
    session: AsyncSession,
    *,
    user_id: str,
    tenant_id: str,
    memory_a: uuid.UUID | None,
    memory_b: uuid.UUID | None,
    distance: float,
    resolution: str,
    resolved_belief: str | None,
    resolved_memory_id: uuid.UUID | None,
    rationale: str | None,
) -> ConflictLog:
    entry = ConflictLog(
        user_id=user_id,
        tenant_id=tenant_id,
        memory_a=memory_a,
        memory_b=memory_b,
        semantic_distance=distance,
        resolution=resolution,
        resolved_belief=resolved_belief,
        resolved_memory_id=resolved_memory_id,
        rationale=rationale,
    )
    session.add(entry)
    await session.flush()
    return entry
