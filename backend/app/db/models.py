"""Phase-0 baseline schema. Summary contract: contracts/db.md (update together)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from findesk_shared import uuid7
from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
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
    # monthly|quarterly — sets the IMS deemed-acceptance grace window. Defaults
    # to the shorter one so an unconfigured tenant is warned early, not late.
    gst_filing_frequency: Mapped[str] = mapped_column(
        String(10), default="monthly", server_default="monthly"
    )
    # business|personal — selects LeakRadar's exclusion list. A business book
    # must never rank payroll as a leak; a personal one must never rank an EMI.
    leak_mode: Mapped[str] = mapped_column(
        String(10), default="business", server_default="business"
    )


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
    # Udyam-register verification (F4): the verified category — when present —
    # beats the self-declared tag for §15/43B(h) scoping; the human tag is
    # never overwritten, both are shown
    msme_verified_category: Mapped[str | None] = mapped_column(String(10), nullable=True)
    msme_verified_urn: Mapped[str | None] = mapped_column(String(25), nullable=True)
    msme_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    category_code: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    # source: rule | memory | human
    category_source: Mapped[str | None] = mapped_column(String(12), nullable=True)
    category_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class ChartAccount(TimestampedTenanted, Base):
    __tablename__ = "chart_of_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(12))  # expense|income|asset|liability|equity


class Invoice(TimestampedTenanted, Base):
    __tablename__ = "invoices"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    counterparty_id: Mapped[str] = mapped_column(ForeignKey("counterparties.id"), index=True)
    number: Mapped[str] = mapped_column(String(50))
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open|paid
    # MSME Act day-zero; falls back to issue_date when not recorded
    acceptance_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Bill(TimestampedTenanted, Base):
    """A payable we owe a vendor — the 43B(h)/§15 buyer-side mirror of Invoice."""

    __tablename__ = "bills"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    counterparty_id: Mapped[str] = mapped_column(ForeignKey("counterparties.id"), index=True)
    number: Mapped[str] = mapped_column(String(50))
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount_paise: Mapped[int] = mapped_column(BigInteger)  # original bill amount
    # unpaid portion — §16 interest and 43B(h) exposure run on THIS, not the
    # original; source syncs (Tally) update it on re-pull
    outstanding_paise: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open|paid
    # MSME Act day-zero; falls back to issue_date when not recorded
    acceptance_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PaymentPromise(TimestampedTenanted, Base):
    """A client's promise-to-pay on one receivable (F3 outcome loop).

    Settlement classifies it kept/broken deterministically when recon marks
    the invoice paid; both the lateness and the promise outcome are written
    back to Recall so the forecast's recalled behavior stays live, not
    seed-only.
    """

    __tablename__ = "payment_promises"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    promised_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open|kept|broken
    source: Mapped[str] = mapped_column(String(20), default="manual")
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ImsRecord(TimestampedTenanted, Base):
    """A supplier-filed document in the tenant's GST IMS queue (F1).

    Sync is upsert-by-record_key; a decided state (accepted/rejected) is
    terminal for sync — re-pulls refresh pending rows only, mirroring the
    bills 'paid is terminal' rule. State changes execute only inside
    decide_approval with a minted token.
    """

    __tablename__ = "ims_records"
    __table_args__ = (UniqueConstraint("tenant_id", "record_key", name="uq_ims_tenant_key"),)

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    record_key: Mapped[str] = mapped_column(String(120))  # gstin:doc_type:number
    supplier_gstin: Mapped[str] = mapped_column(String(15))
    supplier_name: Mapped[str] = mapped_column(String(200))
    doc_type: Mapped[str] = mapped_column(String(12), default="invoice")
    doc_number: Mapped[str] = mapped_column(String(50))
    doc_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period: Mapped[str] = mapped_column(String(7))  # e.g. "2026-07"
    taxable_value_paise: Mapped[int] = mapped_column(BigInteger)
    tax_paise: Mapped[int] = mapped_column(BigInteger)  # the ITC at stake
    total_paise: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    match_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    matched_bill_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(10), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)


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


class Forecast(TimestampedTenanted, Base):
    """B3: one versioned forecast run (lines in ForecastLine)."""

    __tablename__ = "forecasts"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(36))
    horizon_weeks: Mapped[int] = mapped_column(Integer)
    opening_balance_paise: Mapped[int] = mapped_column(BigInteger)
    weekly_outflow_paise: Mapped[int] = mapped_column(BigInteger)
    outflow_basis: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    gap: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    narrative: Mapped[list[str]] = mapped_column(JSON)


class ForecastLine(TimestampedTenanted, Base):
    __tablename__ = "forecast_lines"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    forecast_id: Mapped[str] = mapped_column(ForeignKey("forecasts.id"), index=True)
    scenario: Mapped[str] = mapped_column(String(10))
    week: Mapped[int] = mapped_column(Integer)
    week_start: Mapped[str] = mapped_column(String(10))
    inflow_paise: Mapped[int] = mapped_column(BigInteger)
    outflow_paise: Mapped[int] = mapped_column(BigInteger)
    closing_paise: Mapped[int] = mapped_column(BigInteger)
    drivers: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class WcAction(TimestampedTenanted, Base):
    """B4: one ranked working-capital option (recommend-only until approved)."""

    __tablename__ = "wc_actions"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(10), index=True)  # treds|collect|retime
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(50))
    client: Mapped[str] = mapped_column(String(200))
    unlock_paise: Mapped[int] = mapped_column(BigInteger)
    cost_paise: Mapped[int] = mapped_column(BigInteger)
    rank: Mapped[int] = mapped_column(Integer)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    # proposed | approval_requested | executed | rejected | stale
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    execution: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class StatutoryClock(TimestampedTenanted, Base):
    """B2: one MSME-Act 45-day clock per open receivable (engine-computed)."""

    __tablename__ = "statutory_clocks"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), unique=True)
    acceptance_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    statutory_due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    overdue_days: Mapped[int] = mapped_column(Integer, default=0)
    accrued_interest_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    annual_rate_bps: Mapped[int] = mapped_column(Integer)
    escalation_level: Mapped[str] = mapped_column(String(20), default="none", index=True)
    # highest rung an enforcement artifact has been prepared for (no re-fires)
    last_enforced_level: Mapped[str] = mapped_column(String(20), default="none")


class Anomaly(TimestampedTenanted, Base):
    """A6 anomaly cards — duplicates, overcharges, out-of-pattern spend."""

    __tablename__ = "anomalies"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # duplicate|overcharge|out_of_pattern
    severity: Mapped[str] = mapped_column(String(8), default="medium")  # low|medium|high
    vendor_label: Mapped[str] = mapped_column(String(80))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)  # txn refs, amounts, baseline
    recommended_action: Mapped[str] = mapped_column(String(300))
    recoverable_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)  # stable across rescans


class Subscription(TimestampedTenanted, Base):
    """A recurring vendor series — LeakRadar's unit of work.

    Distinct in grain from ``Anomaly``: an anomaly is a finding about one
    transaction, a subscription is a *series* with a lifecycle (active →
    drifted → stopped). Upsert-by-vendor_slug, so a rescan refreshes rather
    than duplicates, and ``usage`` survives rescans because it is the one field
    a human owns.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "vendor_slug", name="uq_subscription_tenant_vendor"),
    )

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    vendor_slug: Mapped[str] = mapped_column(String(120))
    vendor_label: Mapped[str] = mapped_column(String(120))
    category_code: Mapped[str | None] = mapped_column(String(40), nullable=True)

    cadence: Mapped[str] = mapped_column(String(14), index=True)
    period_days: Mapped[int] = mapped_column(Integer, default=0)
    periods_per_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurrences: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_expected: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)

    amount_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    latest_amount_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    run_rate_paise: Mapped[int] = mapped_column(BigInteger, default=0)

    drift_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    drift_paise_per_year: Mapped[int] = mapped_column(BigInteger, default=0)
    duplicate_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    leak_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    score_components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recoverable_paise_per_year: Mapped[int] = mapped_column(BigInteger, default=0)

    reason: Mapped[str] = mapped_column(String(400), default="")
    recommended_action: Mapped[str] = mapped_column(String(300), default="")
    narrative: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # LLM-written {subject, body, kind} for the approval draft; produced by the
    # scan (never in a request handler) and always human-approved before sending
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # the one field a human owns: in_use | unused | None (never asked)
    usage: Mapped[str | None] = mapped_column(String(10), nullable=True)
    usage_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Conflict(TimestampedTenanted, Base):
    """A4 conflict cards — materialized from Recall's conflict log."""

    __tablename__ = "conflicts"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    claim_kind: Mapped[str] = mapped_column(String(30), default="belief")
    scope_key: Mapped[str] = mapped_column(String(80), index=True)  # e.g. client:<id>
    claim_a: Mapped[dict[str, Any]] = mapped_column(JSON)  # {memory_id, content, confidence}
    claim_b: Mapped[dict[str, Any]] = mapped_column(JSON)
    engine_view: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # distance, default
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)
    resolution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resolver_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    memory_conflict_id: Mapped[str] = mapped_column(String(36), unique=True)


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
