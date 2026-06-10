"""SQLAlchemy ORM models — the relational + vector source of truth.

The provenance *graph* lives in Neo4j (see :mod:`recall.db.neo4j_store`); these
tables hold memory units, their embeddings (pgvector), conflict logs, sessions,
audit logs, and prefetch telemetry.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from recall.config import get_settings


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# Memory tiers and lifecycle states are stored as plain strings (validated in the
# domain layer) to keep migrations simple and avoid native enum churn.
TIERS = ("episodic", "semantic", "procedural")
STATUSES = ("active", "tombstoned", "crystallized")
SCOPES = ("private", "team", "global", "user-owned")


class MemoryUnit(Base):
    """A single unit of memory across any tier.

    ``strength`` is the decaying retrieval-priority axis; ``confidence`` is the
    orthogonal epistemic-trust axis. ``strength_updated_at`` records when
    ``strength`` was last materialized so the decay function can compute the
    current value lazily as ``strength * exp(-lambda * dt)``.
    """

    __tablename__ = "memory_units"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(128), default="default", index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    tier: Mapped[str] = mapped_column(String(16), index=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(get_settings().embedding_dim))

    strength: Mapped[float] = mapped_column(Float, default=1.0)
    strength_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decay_lambda: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.6)

    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    scope: Mapped[str] = mapped_column(String(16), default="private", index=True)
    team_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    cluster: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extra: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    retrieval_count: Mapped[int] = mapped_column(Integer, default=0)
    last_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    corroboration_count: Mapped[int] = mapped_column(Integer, default=0)
    last_referenced_session: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_now
    )

    __table_args__ = (
        Index("ix_memory_active_lookup", "tenant_id", "user_id", "tier", "status"),
        # HNSW index for cosine similarity search over embeddings.
        Index(
            "ix_memory_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class ConflictLog(Base):
    """A permanent record of a detected and resolved belief conflict."""

    __tablename__ = "conflict_log"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(128), default="default", index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    memory_a: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    memory_b: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    semantic_distance: Mapped[float] = mapped_column(Float)

    # resolution: auto_resolved | flagged | merged
    resolution: Mapped[str] = mapped_column(String(32))
    resolved_belief: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), default="default", index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_now
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(128), default="default", index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tool_calls: Mapped[list[ToolCall]] = relationship(back_populates="run", cascade="all, delete")


class ToolCall(Base):
    __tablename__ = "tool_calls"

    call_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.run_id", ondelete="CASCADE")
    )
    tool_name: Mapped[str] = mapped_column(String(128))
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[AgentRun] = relationship(back_populates="tool_calls")


class PrefetchEvent(Base):
    """Telemetry for predictive prefetching; ``consumed`` drives adaptive tuning."""

    __tablename__ = "prefetch_events"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(128), default="default", index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    predicted_cluster: Mapped[str] = mapped_column(String(64))
    num_staged: Mapped[int] = mapped_column(Integer, default=0)
    consumed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
