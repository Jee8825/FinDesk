"""Phase-0 baseline schema. Summary contract: contracts/db.md (update together)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from findesk_shared import uuid7
from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, String, UniqueConstraint
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


# ---------------------------------------------------------------- books (Phase 1)


class Counterparty(TimestampedTenanted, Base):
    __tablename__ = "counterparties"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # vendor|client|both
    name: Mapped[str] = mapped_column(String(200))
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    msme_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contacts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class BankAccount(TimestampedTenanted, Base):
    __tablename__ = "bank_accounts"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    bank: Mapped[str] = mapped_column(String(100))
    account_ref: Mapped[str] = mapped_column(String(50))  # masked, presentation only
    source: Mapped[str] = mapped_column(String(10), default="upload")  # upload|aa|api


class BankTransaction(TimestampedTenanted, Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (UniqueConstraint("bank_account_id", "dedupe_hash"),)

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    bank_account_id: Mapped[str] = mapped_column(ForeignKey("bank_accounts.id"), index=True)
    external_ref: Mapped[str] = mapped_column(String(100))
    value_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    direction: Mapped[str] = mapped_column(String(2))  # cr|dr
    narration: Mapped[str] = mapped_column(String(500))
    counterparty_hint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dedupe_hash: Mapped[str] = mapped_column(String(64))
    source: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    match_status: Mapped[str] = mapped_column(String(12), default="unmatched", index=True)


class Invoice(TimestampedTenanted, Base):
    __tablename__ = "invoices"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    counterparty_id: Mapped[str] = mapped_column(ForeignKey("counterparties.id"), index=True)
    number: Mapped[str] = mapped_column(String(50))
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open|paid


class Match(TimestampedTenanted, Base):
    __tablename__ = "matches"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    bank_transaction_id: Mapped[str] = mapped_column(
        ForeignKey("bank_transactions.id"), index=True
    )
    target_kind: Mapped[str] = mapped_column(String(10), default="invoice")
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(15), default="full")  # full|partial|tds_adjusted
    confidence: Mapped[float] = mapped_column(Float)
    matched_by: Mapped[str] = mapped_column(String(10), default="agent")  # agent|human
    critic_verdict: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="proposed")  # proposed|committed


class LedgerEntry(TimestampedTenanted, Base):
    __tablename__ = "ledger_entries"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSON)  # double-entry, sums to zero
    origin: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # {kind, match_id, run_id}


class AuditLog(TimestampedTenanted, Base):
    """Append-only, hash-chained. Never UPDATE/DELETE (enforced by role in prod)."""

    __tablename__ = "audit_log"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor: Mapped[dict[str, Any]] = mapped_column(JSON)  # {kind: user|agent, id, run_id?}
    action: Mapped[str] = mapped_column(String(50), index=True)
    entity_ref: Mapped[str] = mapped_column(String(80), index=True)  # "<kind>:<id>"
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    row_hash: Mapped[str] = mapped_column(String(64))


class Approval(TimestampedTenanted, Base):
    """The approval queue — the only path to executing a consequential action."""

    __tablename__ = "approvals"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    action_kind: Mapped[str] = mapped_column(String(40), index=True)  # e.g. commit_match
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    action_hash: Mapped[str] = mapped_column(String(64))  # sha256(canonical payload)
    requested_by: Mapped[dict[str, Any]] = mapped_column(JSON)  # {kind: agent, run_id}
    policy_verdicts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    decider_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rationale: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # single-use


class Document(TimestampedTenanted, Base):
    __tablename__ = "documents"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # bank_statement|invoice|report
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(500))  # dev: var/uploads; prod: object store
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
