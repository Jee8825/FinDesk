"""Deterministic fake providers for integration tests (no API keys needed).

* ``FakeEmbedder`` — a hashing bag-of-words embedder. Lexically similar texts get
  similar vectors, so cosine search and conflict detection behave predictably.
* ``FakeLLM`` — returns queued extraction results and a fixed conflict
  resolution, and "summarizes" by truncation.
"""

from __future__ import annotations

import hashlib
import math

from recall.core.conflict import ResolutionOutput
from recall.core.ingestion import ExtractionOutput
from recall.core.types import ExtractedFact


class FakeEmbedder:
    def __init__(self, dim: int) -> None:
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for token in text.lower().split():
            idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim
            v[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]


class FakeLLM:
    def __init__(self, fact_batches: list[list[ExtractedFact]] | None = None) -> None:
        self._batches = list(fact_batches or [])

    def queue_facts(self, facts: list[ExtractedFact]) -> None:
        self._batches.append(facts)

    async def complete_structured(self, prompt, schema, *, role="heavy", **_):  # noqa: ANN001
        if schema is ExtractionOutput:
            facts = self._batches.pop(0) if self._batches else []
            return ExtractionOutput(facts=facts)
        if schema is ResolutionOutput:
            # Deterministic: newest belief supersedes; echo it back.
            return ResolutionOutput(
                resolution="auto_resolved",
                resolved_belief="User primary backend language is TypeScript",
                rationale="newer statement supersedes the older preference",
            )
        raise NotImplementedError(schema)

    async def complete(self, prompt: str, *, role="light", max_tokens=None, **_):  # noqa: ANN001
        return "compressed memory"

    async def classify(self, prompt: str, labels: list[str], **_):  # noqa: ANN001
        return labels[0]
