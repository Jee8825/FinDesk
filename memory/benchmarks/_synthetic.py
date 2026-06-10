"""Synthetic data + tiny fake providers for offline benchmarks."""

from __future__ import annotations

import hashlib
import math
import random
from datetime import UTC, datetime, timedelta

from recall.db.models import MemoryUnit

DIM = 64


def embed(text: str, dim: int = DIM) -> list[float]:
    v = [0.0] * dim
    for token in text.lower().split():
        idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % dim
        v[idx] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


class FakeSummarizer:
    """Light-LLM stand-in that compresses by keeping the first few words."""

    async def complete(self, prompt: str, *, role="light", max_tokens=None, **_):  # noqa: ANN001
        # The content is appended after the template; take a short head.
        tail = prompt.strip().splitlines()[-1]
        return " ".join(tail.split()[:6])


def make_unit(
    content: str,
    *,
    age_days: float,
    decay_lambda: float,
    strength: float = 1.0,
    dim: int = DIM,
) -> MemoryUnit:
    now = datetime.now(UTC)
    created = now - timedelta(days=age_days)
    u = MemoryUnit(
        user_id="bench",
        tier="semantic",
        content=content,
        embedding=embed(content, dim),
        decay_lambda=decay_lambda,
        confidence=0.7,
        strength=strength,
        strength_updated_at=created,
    )
    u.created_at = created
    u.last_retrieved_at = None
    return u


def seeded_random(seed: int = 42) -> random.Random:
    return random.Random(seed)
