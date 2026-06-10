"""Shared domain types (Pydantic DTOs) used by the engine, API, and SDK.

These are the wire/contract types. They are deliberately separate from the
SQLAlchemy models in :mod:`recall.db.models` so the storage schema can evolve
independently of the public contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["episodic", "semantic", "procedural"]
Status = Literal["active", "tombstoned", "crystallized"]
Scope = Literal["private", "team", "global", "user-owned"]
Resolution = Literal["auto_resolved", "flagged", "merged", "none"]


class MemoryUnitDTO(BaseModel):
    """A memory unit as returned to callers."""

    id: uuid.UUID
    user_id: str
    tier: Tier
    content: str
    strength: float = Field(description="Current decayed retrieval-priority strength.")
    confidence: float = Field(description="Epistemic trust, 0-1.")
    status: Status
    scope: Scope
    team_id: str | None = None
    cluster: str | None = None
    retrieval_count: int = 0
    created_at: datetime
    last_retrieved_at: datetime | None = None


class IngestRequest(BaseModel):
    user_id: str
    session_id: str
    content: str = Field(description="Raw conversation text or message to extract memory from.")
    scope: Scope = "private"
    team_id: str | None = None
    tenant_id: str = "default"


class ExtractedFact(BaseModel):
    """One fact extracted from raw content by the heavy LLM."""

    content: str
    tier: Tier = "semantic"
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    cluster: str | None = Field(
        default=None,
        description="Coarse topic tag (e.g. cloud-deployment, coding-preferences).",
    )


class IngestResult(BaseModel):
    units: list[MemoryUnitDTO]
    conflicts_detected: int = 0


class RetrieveRequest(BaseModel):
    user_id: str
    query: str
    token_budget: int = 2000
    scope: Scope | None = None
    team_id: str | None = None
    session_id: str | None = None
    tenant_id: str = "default"


class RetrievedMemory(BaseModel):
    id: uuid.UUID
    content: str
    tier: Tier
    score: float = Field(description="relevance x recency x strength composite.")
    strength: float
    confidence: float
    summarized: bool = Field(
        default=False, description="True if compressed by the budget-packer to fit."
    )


class RetrieveResult(BaseModel):
    memories: list[RetrievedMemory]
    tokens_used: int
    token_budget: int
    cache_hit: bool = False


class WhyResult(BaseModel):
    memory_id: uuid.UUID
    confidence: float | None
    status: str | None = None
    explanation: str = Field(description="Plain-language reconstruction of the evidence chain.")
    evidence: list[dict] = Field(default_factory=list)
    resolved_from: list[str] = Field(default_factory=list)


class PromoteRequest(BaseModel):
    memory_id: uuid.UUID
    scope: Scope
    team_id: str | None = None
    is_orchestrator: bool = Field(
        default=False, description="Required true to promote a memory to global scope."
    )


class PrefetchRequest(BaseModel):
    user_id: str
    session_id: str
    recent_turns: list[str] = Field(description="Last few conversation turns.")
    tenant_id: str = "default"


class PrefetchResult(BaseModel):
    predicted_cluster: str
    staged: int


class ConsolidateRequest(BaseModel):
    user_id: str
    tenant_id: str = "default"


class ConflictDTO(BaseModel):
    id: uuid.UUID
    user_id: str
    semantic_distance: float
    resolution: Resolution
    resolved_belief: str | None
    rationale: str | None
    created_at: datetime
    # FinDesk additive extension (ADR-0002): both sides of the conflict, so
    # consumers can render/resolve without touching the store directly.
    memory_a: uuid.UUID | None = None
    memory_b: uuid.UUID | None = None
