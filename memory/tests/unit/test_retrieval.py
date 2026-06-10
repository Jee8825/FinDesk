"""Unit tests for retrieval scoring and the token-budget packer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from recall.core import retrieval
from recall.db.models import MemoryUnit


def _unit(content: str, *, strength: float = 1.0, lam: float = 0.02) -> MemoryUnit:
    now = datetime.now(UTC)
    u = MemoryUnit(
        user_id="u1",
        tier="semantic",
        content=content,
        embedding=[0.0, 0.0],
        decay_lambda=lam,
        confidence=0.6,
        strength=strength,
        strength_updated_at=now,
    )
    u.created_at = now
    u.last_retrieved_at = None
    return u


class FakeLLM:
    """Light LLM stub: 'compresses' by truncating to a few words."""

    async def complete(self, prompt: str, *, role="light", max_tokens=None, **_):  # noqa: ANN001
        # The content to summarize is the tail of the rendered prompt.
        return "summary short"

    async def complete_structured(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    async def classify(self, *a, **k):  # pragma: no cover
        raise NotImplementedError


def test_score_orders_by_relevance_recency_strength():
    a = _unit("a", strength=1.0)
    b = _unit("b", strength=0.2)
    # a is more relevant (smaller distance) AND stronger -> ranks first.
    scored = retrieval.score_candidates([(a, 0.1), (b, 0.5)])
    assert scored[0].unit is a
    assert scored[0].score > scored[1].score


def test_strength_factor_affects_score():
    strong = _unit("s", strength=1.0)
    weak = _unit("w", strength=0.1)
    # Same distance; stronger memory wins.
    scored = retrieval.score_candidates([(weak, 0.2), (strong, 0.2)])
    assert scored[0].unit is strong


@pytest.mark.asyncio
async def test_packer_respects_budget_and_compresses():
    big = _unit("word " * 200)  # ~200 tokens
    scored = retrieval.score_candidates([(big, 0.05)])
    # Budget too small for the full memory -> packer compresses it.
    items, used = await retrieval.pack_to_budget(scored, token_budget=10, llm=FakeLLM())
    assert used <= 10
    assert len(items) == 1
    assert items[0].summarized is True


@pytest.mark.asyncio
async def test_packer_keeps_full_when_it_fits():
    small = _unit("just a short memory")
    scored = retrieval.score_candidates([(small, 0.05)])
    items, used = await retrieval.pack_to_budget(scored, token_budget=2000, llm=FakeLLM())
    assert items[0].summarized is False
    assert used > 0
