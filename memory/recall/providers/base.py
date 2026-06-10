"""Provider-agnostic LLM and embedding interfaces.

Recall never imports a vendor SDK directly from engine code. Instead the engine
depends on these two protocols, and a concrete provider is selected at runtime
from configuration (see :func:`recall.providers.get_llm` /
:func:`recall.providers.get_embedder`).

Two LLM *roles* are distinguished throughout the engine:

* **heavy** — extraction, consolidation, conflict resolution. Quality matters.
* **light** — retrieval scoring, compression, prefetch intent. Latency matters.

A provider maps each role to a concrete model id from settings.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

Role = Literal["heavy", "light"]
T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    """Minimal surface the engine needs from a chat-completion model."""

    async def complete(
        self,
        prompt: str,
        *,
        role: Role = "heavy",
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        """Return a free-text completion."""
        ...

    async def complete_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        role: Role = "heavy",
        system: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        """Return a completion parsed and validated into ``schema``.

        Implementations request JSON output, validate against the Pydantic
        model, and retry on parse failure (see ``_json_with_retry``).
        """

    async def classify(
        self,
        prompt: str,
        labels: list[str],
        *,
        role: Role = "light",
        system: str | None = None,
    ) -> str:
        """Return exactly one label from ``labels`` (cheap, low-latency path)."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Minimal surface the engine needs from an embedding model."""

    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors of length ``self.dim``."""


class ProviderError(RuntimeError):
    """Raised when a provider call fails after retries.

    The engine catches this to trigger queue-and-retry fallbacks (e.g. ingestion
    degrades gracefully when the heavy model is unavailable).
    """

    def __init__(self, provider: str, detail: str, raw: Any | None = None) -> None:
        super().__init__(f"[{provider}] {detail}")
        self.provider = provider
        self.detail = detail
        self.raw = raw
