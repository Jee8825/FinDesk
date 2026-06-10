"""Retrieval: score candidates and pack them into a token budget.

Scoring composes three signals:

    score = relevance * recency * strength

* relevance — cosine similarity to the query (1 - distance)
* recency   — mild exponential preference for recently created/touched memories
* strength  — the current decayed retrieval-priority value

The budget-packer then maximizes information coverage within ``token_budget``:
it greedily takes the highest-scoring memories at full length, and when a memory
does not fit, it asks the light LLM to summarize it so more signal fits. This is
an optimization (packing), not a simple relevance filter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from recall.core import decay, prompts
from recall.core.tokens import count_tokens
from recall.db.models import MemoryUnit
from recall.providers import LLMProvider

# Recency decay used purely for *ranking* (separate from memory strength decay).
_RECENCY_K = 0.05


@dataclass
class ScoredMemory:
    unit: MemoryUnit
    relevance: float
    recency: float
    strength: float
    score: float


def _recency(unit: MemoryUnit, now: datetime) -> float:
    anchor = unit.last_retrieved_at or unit.created_at
    age_days = decay.elapsed_days(anchor, now)
    return math.exp(-_RECENCY_K * age_days)


def score_candidates(
    candidates: list[tuple[MemoryUnit, float]], now: datetime | None = None
) -> list[ScoredMemory]:
    """Score and sort candidate ``(unit, cosine_distance)`` pairs, best first."""
    now = now or datetime.now(UTC)
    scored: list[ScoredMemory] = []
    for unit, distance in candidates:
        relevance = max(0.0, 1.0 - distance)
        strength = decay.current_strength(
            unit.strength, unit.decay_lambda, unit.strength_updated_at, now
        )
        recency = _recency(unit, now)
        scored.append(
            ScoredMemory(
                unit=unit,
                relevance=relevance,
                recency=recency,
                strength=strength,
                score=relevance * recency * strength,
            )
        )
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


@dataclass
class PackedItem:
    unit: MemoryUnit
    text: str
    score: float
    summarized: bool
    tokens: int


async def pack_to_budget(
    scored: list[ScoredMemory],
    token_budget: int,
    llm: LLMProvider,
    *,
    compress: bool = True,
) -> tuple[list[PackedItem], int]:
    """Pack scored memories into ``token_budget`` tokens, summarizing to fit more.

    Returns ``(items, tokens_used)``. Higher-scoring memories are placed first at
    full length; once the budget tightens, remaining memories are compressed via
    the light LLM and included only if the summary fits.
    """
    items: list[PackedItem] = []
    used = 0
    for sm in scored:
        full = sm.unit.content
        full_tokens = count_tokens(full)
        if used + full_tokens <= token_budget:
            items.append(PackedItem(sm.unit, full, sm.score, False, full_tokens))
            used += full_tokens
            continue

        if not compress:
            continue

        # Try to fit a compressed version.
        try:
            summary = (
                await llm.complete(
                    prompts.render("summarize", content=full), role="light", max_tokens=80
                )
            ).strip()
        except Exception:  # noqa: BLE001 - compression is best-effort
            summary = full[: max(0, (token_budget - used) * 4)]
        sum_tokens = count_tokens(summary)
        if summary and used + sum_tokens <= token_budget:
            items.append(PackedItem(sm.unit, summary, sm.score, True, sum_tokens))
            used += sum_tokens
        # else: skip this memory; keep scanning for smaller ones that may fit.
    return items, used
