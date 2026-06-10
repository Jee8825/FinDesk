"""Phase-0 baseline schema. Summary contract: contracts/db.md (update together)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from findesk_shared import uuid7
from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampedTenanted:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Tenant(TimestampedTenanted, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200))
    plan: Mapped[str] = mapped_column(String(20), default="startup")


class User(TimestampedTenanted, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))


class Membership(TimestampedTenanted, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # owner|accountant|ca|viewer


class AgentRun(TimestampedTenanted, Base):
    __tablename__ = "agent_runs"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    graph: Mapped[str] = mapped_column(String(50), index=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentStep(TimestampedTenanted, Base):
    __tablename__ = "agent_steps"

    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    step_id: Mapped[str] = mapped_column(String(36), unique=True)  # idempotency key
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))  # started|finished|failed
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
