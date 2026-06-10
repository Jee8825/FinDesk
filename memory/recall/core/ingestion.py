"""Ingestion: turn raw conversation into embedded, tiered memory units.

The heavy LLM extracts durable facts (see ``prompts/extraction.md``); each fact
is embedded and written as a memory unit. Conflict detection and provenance are
orchestrated by the engine façade (:mod:`recall.core.engine`) so this module
stays focused on extraction + embedding + persistence.
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from recall.config import Settings
from recall.core import prompts, repository
from recall.core.types import ExtractedFact, Scope
from recall.db.models import MemoryUnit
from recall.logging import get_logger
from recall.providers import EmbeddingProvider, LLMProvider, ProviderError

log = get_logger(__name__)


class ExtractionOutput(BaseModel):
    """Structured output schema for the extraction LLM call."""

    facts: list[ExtractedFact]


async def extract_facts(llm: LLMProvider, content: str) -> list[ExtractedFact]:
    """Run the heavy LLM to extract durable facts from raw text.

    Returns an empty list (rather than raising) if the provider is unavailable,
    so ingestion degrades gracefully and the caller can queue-and-retry.
    """
    prompt = prompts.render("extraction", content=content)
    try:
        out = await llm.complete_structured(prompt, ExtractionOutput, role="heavy")
    except ProviderError as exc:
        log.warning("ingestion.extract_failed", error=str(exc))
        return []
    return out.facts


async def persist_fact(
    session: AsyncSession,
    *,
    fact: ExtractedFact,
    embedding: list[float],
    user_id: str,
    tenant_id: str,
    scope: Scope,
    team_id: str | None,
    session_id: str | None,
    settings: Settings,
) -> MemoryUnit:
    return await repository.insert_memory(
        session,
        user_id=user_id,
        tenant_id=tenant_id,
        tier=fact.tier,
        content=fact.content,
        embedding=embedding,
        decay_lambda=settings.decay_lambda(fact.tier),
        confidence=fact.confidence,
        scope=scope,
        team_id=team_id,
        cluster=fact.cluster,
        source_session_id=session_id,
    )


async def embed_facts(
    embedder: EmbeddingProvider, facts: list[ExtractedFact]
) -> list[list[float]]:
    if not facts:
        return []
    return await embedder.embed([f.content for f in facts])
