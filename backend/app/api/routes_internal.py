"""Internal worker ↔ backend API (shared-token auth, never exposed publicly).

The agents layer has no DB access by rule; these endpoints are its only path
to app data. Every request is tenant-scoped explicitly — the worker passes the
tenant_id from the job envelope, and rows are filtered server-side regardless.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

import anyio
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.db import session_scope
from app.db.books_repo import BooksRepo
from app.db.repositories import RunRepo
from app.services.forecast_trigger import trigger_forecast_recompute
from app.services.recon import route_proposal

router = APIRouter(prefix="/internal", tags=["internal"])


def _check_token(token: str | None) -> None:
    expected = get_settings().internal_api_token
    if token is None or not secrets.compare_digest(token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad internal token")


class DocumentContent(BaseModel):
    document_id: str
    filename: str
    content: str


@router.get("/documents/{document_id}", response_model=DocumentContent)
async def document_content(
    document_id: str, tenant_id: str, x_internal_token: str | None = Header(None)
) -> DocumentContent:
    _check_token(x_internal_token)
    async with session_scope() as session:
        doc = await BooksRepo(session).document(document_id, tenant_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    path = anyio.Path(doc.storage_path)
    if not await path.exists():
        raise HTTPException(status.HTTP_410_GONE, "document bytes missing")
    content = await path.read_text(errors="replace")
    return DocumentContent(document_id=doc.id, filename=doc.filename, content=content)


class TxnIngest(BaseModel):
    tenant_id: str
    rows: list[dict[str, Any]]  # NormalizedTxn + dedupe_hash, per contracts/tools.md


class TxnIngestOut(BaseModel):
    inserted: int
    skipped: int
    rejected: int = 0  # malformed rows dropped (never a 500)


@router.post("/recon/transactions", response_model=TxnIngestOut)
async def ingest_transactions(
    body: TxnIngest, x_internal_token: str | None = Header(None)
) -> TxnIngestOut:
    _check_token(x_internal_token)
    async with session_scope() as session:
        repo = BooksRepo(session)
        account = await repo.default_bank_account(body.tenant_id)
        if account is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "tenant has no bank account")
        from findesk_shared import uuid7

        # whitelist: tool payloads may carry extra fields (e.g. balance_paise)
        # that are not persisted columns
        columns = (
            "external_ref",
            "amount_paise",
            "direction",
            "narration",
            "counterparty_hint",
            "dedupe_hash",
            "source",
        )
        required = ("value_date", "amount_paise", "direction", "narration", "dedupe_hash")
        rows = []
        rejected = 0
        for row in body.rows:
            if any(k not in row for k in required):
                rejected += 1
                continue
            try:
                value_date = datetime.fromisoformat(str(row["value_date"]))
            except ValueError:
                rejected += 1
                continue
            rows.append(
                {
                    "id": uuid7(),
                    "tenant_id": body.tenant_id,
                    "bank_account_id": account.id,
                    **{k: row[k] for k in columns if k in row},
                    "value_date": value_date,
                }
            )
        if rejected:
            import logging

            logging.getLogger(__name__).warning(
                "ingest: rejected %d malformed rows for tenant %s", rejected, body.tenant_id
            )
        inserted, skipped = await repo.insert_transactions_deduped(rows)
    return TxnIngestOut(inserted=inserted, skipped=skipped, rejected=rejected)


class ReconContext(BaseModel):
    unmatched: list[dict[str, Any]]
    open_invoices: list[dict[str, Any]]
    counterparties: list[dict[str, Any]]
    uncategorized_debits: list[dict[str, Any]] = []
    valid_category_codes: list[str] = []


@router.get("/recon/context", response_model=ReconContext)
async def recon_context(
    tenant_id: str, x_internal_token: str | None = Header(None)
) -> ReconContext:
    _check_token(x_internal_token)
    async with session_scope() as session:
        repo = BooksRepo(session)
        txns = await repo.unmatched_transactions(tenant_id)
        invoices = await repo.open_invoices(tenant_id)
        parties = await repo.counterparties(tenant_id)
        debits = await repo.uncategorized_debits(tenant_id)
        codes = [c.code for c in await repo.chart_accounts(tenant_id)]
    return ReconContext(
        uncategorized_debits=[
            {
                "id": t.id,
                "direction": t.direction,
                "narration": t.narration,
                "counterparty_hint": t.counterparty_hint,
                "category_code": t.category_code,
            }
            for t in debits
        ],
        valid_category_codes=codes,
        unmatched=[
            {
                "id": t.id,
                "value_date": t.value_date.isoformat(),
                "amount_paise": t.amount_paise,
                "direction": t.direction,
                "narration": t.narration,
                "counterparty_hint": t.counterparty_hint,
            }
            for t in txns
        ],
        open_invoices=[
            {
                "id": i.id,
                "counterparty_id": i.counterparty_id,
                "number": i.number,
                "issue_date": i.issue_date.isoformat(),
                "due_date": i.due_date.isoformat(),
                "amount_paise": i.amount_paise,
            }
            for i in invoices
        ],
        counterparties=[{"id": c.id, "name": c.name, "kind": c.kind} for c in parties],
    )


class CategorizeRequest(BaseModel):
    tenant_id: str
    run_id: str
    items: list[dict[str, Any]]  # {bank_transaction_id, category_code, source, confidence}


class CategorizeOut(BaseModel):
    applied: int
    skipped: int


@router.post("/recon/categorize", response_model=CategorizeOut)
async def categorize_transactions(
    body: CategorizeRequest, x_internal_token: str | None = Header(None)
) -> CategorizeOut:
    _check_token(x_internal_token)
    applied = 0
    async with session_scope() as session:
        repo = BooksRepo(session)
        valid = {c.code for c in await repo.chart_accounts(body.tenant_id)}
        for item in body.items:
            txn_id = item.get("bank_transaction_id")
            if not txn_id or item.get("category_code") not in valid:
                continue
            txn = await repo.transaction(txn_id, body.tenant_id)
            if txn is None:
                continue
            ok = await repo.set_category(
                txn.id,
                code=item["category_code"],
                source=item.get("source", "rule"),
                confidence=float(item.get("confidence", 0.8)),
            )
            applied += 1 if ok else 0
        if applied:
            from app.services.audit import write_audit

            await write_audit(
                session,
                tenant_id=body.tenant_id,
                actor={"kind": "agent", "run_id": body.run_id},
                action="transactions.categorized",
                entity_ref=f"run:{body.run_id}",
                payload={"applied": applied, "items": body.items},
            )
    return CategorizeOut(applied=applied, skipped=len(body.items) - applied)


class AnomalyContext(BaseModel):
    debits: list[dict[str, Any]]


@router.get("/anomalies/context", response_model=AnomalyContext)
async def anomaly_context(
    tenant_id: str, x_internal_token: str | None = Header(None)
) -> AnomalyContext:
    _check_token(x_internal_token)
    async with session_scope() as session:
        debits = await BooksRepo(session).debit_transactions(tenant_id)
    return AnomalyContext(
        debits=[
            {
                "id": t.id,
                "value_date": t.value_date.isoformat(),
                "amount_paise": t.amount_paise,
                "narration": t.narration,
                "counterparty_hint": t.counterparty_hint,
                "category_code": t.category_code,
            }
            for t in debits
        ]
    )


class AnomalyPersist(BaseModel):
    tenant_id: str
    run_id: str
    findings: list[dict[str, Any]]


class AnomalyPersistOut(BaseModel):
    created: int
    existing: int


@router.post("/anomalies", response_model=AnomalyPersistOut)
async def persist_anomalies(
    body: AnomalyPersist, x_internal_token: str | None = Header(None)
) -> AnomalyPersistOut:
    _check_token(x_internal_token)
    from findesk_shared import uuid7
    from sqlalchemy import select

    from app.db.models import Anomaly
    from app.services.audit import write_audit

    created = 0
    async with session_scope() as session:
        known = {
            row.dedupe_key
            for row in await session.scalars(
                select(Anomaly).where(Anomaly.tenant_id == body.tenant_id)
            )
        }
        for f in body.findings:
            dedupe_key = f.get("dedupe_key")
            if not dedupe_key or dedupe_key in known or not f.get("kind"):
                continue  # malformed or duplicate — drop, never 500
            session.add(
                Anomaly(
                    id=uuid7(),
                    tenant_id=body.tenant_id,
                    kind=f["kind"],
                    severity=f.get("severity") or "medium",
                    vendor_label=(f.get("vendor_label") or "unknown")[:80],
                    evidence=f.get("evidence") or {},
                    recommended_action=(f.get("recommended_action") or "")[:300],
                    recoverable_paise=f.get("recoverable_paise"),
                    dedupe_key=dedupe_key,
                )
            )
            created += 1
        if created:
            await write_audit(
                session,
                tenant_id=body.tenant_id,
                actor={"kind": "agent", "run_id": body.run_id},
                action="anomalies.raised",
                entity_ref=f"run:{body.run_id}",
                payload={"created": created},
            )
    return AnomalyPersistOut(created=created, existing=len(body.findings) - created)


class ForecastContext(BaseModel):
    opening_balance_paise: int
    open_invoices: list[dict[str, Any]]
    debits: list[dict[str, Any]]
    open_bills: list[dict[str, Any]] = []  # dated payables → firm outflows


@router.get("/forecast/context", response_model=ForecastContext)
async def forecast_context(
    tenant_id: str, x_internal_token: str | None = Header(None)
) -> ForecastContext:
    _check_token(x_internal_token)
    from sqlalchemy import func, select

    from app.db.models import BankTransaction

    async with session_scope() as session:
        repo = BooksRepo(session)
        # cash position derived from the books: net of all recorded movements
        credits = await session.scalar(
            select(func.coalesce(func.sum(BankTransaction.amount_paise), 0)).where(
                BankTransaction.tenant_id == tenant_id, BankTransaction.direction == "cr"
            )
        )
        debits_sum = await session.scalar(
            select(func.coalesce(func.sum(BankTransaction.amount_paise), 0)).where(
                BankTransaction.tenant_id == tenant_id, BankTransaction.direction == "dr"
            )
        )
        invoices = await repo.open_invoices(tenant_id)
        parties = {c.id: c.name for c in await repo.counterparties(tenant_id)}
        debit_rows = await repo.debit_transactions(tenant_id)
        bills = await repo.open_bills(tenant_id)
    return ForecastContext(
        opening_balance_paise=int(credits) - int(debits_sum),
        open_bills=[
            {
                "number": b.number,
                "vendor": parties.get(b.counterparty_id, "?"),
                "outstanding_paise": b.outstanding_paise,
                "due_date": b.due_date.isoformat(),
            }
            for b in bills
        ],
        open_invoices=[
            {
                "id": i.id,
                "number": i.number,
                "client": parties.get(i.counterparty_id, "?"),
                "client_id": i.counterparty_id,
                "amount_paise": i.amount_paise,
                "due_date": i.due_date.isoformat(),
            }
            for i in invoices
        ],
        debits=[
            {
                "id": t.id,
                "value_date": t.value_date.isoformat(),
                "amount_paise": t.amount_paise,
                "narration": t.narration,
                "counterparty_hint": t.counterparty_hint,
            }
            for t in debit_rows
        ],
    )


class ForecastPersist(BaseModel):
    tenant_id: str
    run_id: str
    result: dict[str, Any]


@router.post("/forecast")
async def persist_forecast(
    body: ForecastPersist, x_internal_token: str | None = Header(None)
) -> dict[str, Any]:
    _check_token(x_internal_token)
    from findesk_shared import uuid7

    from app.db.models import Forecast, ForecastLine

    r = body.result
    async with session_scope() as session:
        forecast = Forecast(
            id=uuid7(),
            tenant_id=body.tenant_id,
            run_id=body.run_id,
            horizon_weeks=r["horizon_weeks"],
            opening_balance_paise=r["opening_balance_paise"],
            weekly_outflow_paise=r["weekly_outflow_paise"],
            outflow_basis=r["outflow_basis"],
            gap=r["gap"],
            narrative=r["narrative"],
        )
        session.add(forecast)
        for scenario, weeks in r["scenarios"].items():
            for week in weeks:
                session.add(
                    ForecastLine(
                        id=uuid7(),
                        tenant_id=body.tenant_id,
                        forecast_id=forecast.id,
                        scenario=scenario,
                        week=week["week"],
                        week_start=week["week_start"],
                        inflow_paise=week["inflow_paise"],
                        outflow_paise=week["outflow_paise"],
                        closing_paise=week["closing_paise"],
                        drivers=week["drivers"],
                    )
                )
    return {"forecast_id": forecast.id}


LADDER_ORDER = ("none", "nudge", "reminder", "act_letter", "samadhaan_prep")
ENFORCED_LEVELS = {"act_letter", "samadhaan_prep"}


class EnforcerContext(BaseModel):
    transitions: list[dict[str, Any]]
    sender_name: str
    tenant_name: str


@router.get("/enforcer/context", response_model=EnforcerContext)
async def enforcer_context(
    tenant_id: str, x_internal_token: str | None = Header(None)
) -> EnforcerContext:
    _check_token(x_internal_token)
    from app.db.repositories import TenantRepo
    from app.services.clocks import recompute_clocks

    async with session_scope() as session:
        repo = BooksRepo(session)
        parties = {c.id: c for c in await repo.counterparties(tenant_id)}
        tenant = await TenantRepo(session).by_id(tenant_id)
        transitions = []
        for inv, clock, snap in await recompute_clocks(session, tenant_id):
            level = snap["escalation_level"]
            if level not in ENFORCED_LEVELS:
                continue
            if LADDER_ORDER.index(level) <= LADDER_ORDER.index(clock.last_enforced_level):
                continue  # already acted on this rung (or higher) — no re-fire
            client = parties.get(inv.counterparty_id)
            transitions.append(
                {
                    "invoice": {
                        "id": inv.id,
                        "number": inv.number,
                        "amount_paise": inv.amount_paise,
                    },
                    "client": {
                        "id": inv.counterparty_id,
                        "name": client.name if client else "?",
                        "emails": (client.contacts or {}).get("emails", []) if client else [],
                    },
                    "clock": snap,
                }
            )
    tenant_name = tenant.name if tenant else "the supplier"
    return EnforcerContext(
        transitions=transitions,
        sender_name=f"Accounts, {tenant_name}",
        tenant_name=tenant_name,
    )


class ActLetterQueue(BaseModel):
    tenant_id: str
    run_id: str
    letter: dict[str, Any]


@router.post("/enforcer/act-letter")
async def queue_act_letter(
    body: ActLetterQueue, x_internal_token: str | None = Header(None)
) -> dict[str, Any]:
    _check_token(x_internal_token)
    from sqlalchemy import select

    from app.db.models import StatutoryClock
    from app.services.approvals import queue_approval

    letter = body.letter
    async with session_scope() as session:
        approval = await queue_approval(
            session,
            tenant_id=body.tenant_id,
            action_kind="send_email",
            action_payload=letter,
            requested_by={"kind": "agent", "run_id": body.run_id},
            policy_verdicts={
                "rule": "statutory escalation letters are always human-gated (P2/P6)",
                "ladder_rung": letter.get("level"),
                "days_overdue": letter.get("days_overdue"),
            },
        )
        clock = await session.scalar(
            select(StatutoryClock).where(
                StatutoryClock.tenant_id == body.tenant_id,
                StatutoryClock.invoice_id == letter["invoice_id"],
            )
        )
        if clock is not None:
            clock.last_enforced_level = letter.get("level", "act_letter")
    return {"queued": True, "approval_id": approval.id}


class SamadhaanPersist(BaseModel):
    tenant_id: str
    run_id: str
    doc: dict[str, Any]


@router.post("/enforcer/samadhaan-prep")
async def persist_samadhaan(
    body: SamadhaanPersist, x_internal_token: str | None = Header(None)
) -> dict[str, Any]:
    _check_token(x_internal_token)
    from findesk_shared import uuid7
    from sqlalchemy import select

    from app.config import get_settings
    from app.db.models import Document, StatutoryClock
    from app.services.audit import write_audit

    doc = body.doc
    if not all(k in doc for k in ("invoice_id", "invoice_number", "title", "body_md")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "incomplete samadhaan doc")
    doc_id = uuid7()
    folder = anyio.Path(get_settings().upload_dir) / body.tenant_id
    path = folder / f"{doc_id}-samadhaan-{doc['invoice_number']}.md"
    # non-blocking write BEFORE the transaction: a failed write aborts cleanly
    # with no DB row; a rolled-back transaction leaves only a harmless file
    try:
        await folder.mkdir(parents=True, exist_ok=True)
        await path.write_text(doc["body_md"], encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status.HTTP_507_INSUFFICIENT_STORAGE, f"could not store document: {exc}"
        ) from exc
    async with session_scope() as session:
        session.add(
            Document(
                id=doc_id,
                tenant_id=body.tenant_id,
                kind="samadhaan_prep",
                filename=path.name,
                content_hash="",
                storage_path=str(path),
                meta={"invoice_id": doc["invoice_id"], "title": doc["title"]},
            )
        )
        await write_audit(
            session,
            tenant_id=body.tenant_id,
            actor={"kind": "agent", "run_id": body.run_id},
            action="samadhaan.prepared",
            entity_ref=f"invoice:{doc['invoice_id']}",
            payload={"document_id": doc_id, "title": doc["title"]},
        )
        clock = await session.scalar(
            select(StatutoryClock).where(
                StatutoryClock.tenant_id == body.tenant_id,
                StatutoryClock.invoice_id == doc["invoice_id"],
            )
        )
        if clock is not None:
            clock.last_enforced_level = "samadhaan_prep"
    return {"document_id": doc_id}


@router.get("/forecast/latest-gap")
async def latest_gap(tenant_id: str, x_internal_token: str | None = Header(None)) -> dict[str, Any]:
    _check_token(x_internal_token)
    from sqlalchemy import select

    from app.db.models import Forecast

    async with session_scope() as session:
        forecast = await session.scalar(
            select(Forecast)
            .where(Forecast.tenant_id == tenant_id)
            .order_by(Forecast.created_at.desc())
            .limit(1)
        )
    return {"gap": forecast.gap if forecast else None}


class WcPersist(BaseModel):
    tenant_id: str
    run_id: str
    options: list[dict[str, Any]]


@router.post("/wc-actions")
async def persist_wc_actions(
    body: WcPersist, x_internal_token: str | None = Header(None)
) -> dict[str, Any]:
    _check_token(x_internal_token)
    from findesk_shared import uuid7
    from sqlalchemy import select

    from app.db.models import WcAction

    created = 0
    async with session_scope() as session:
        # a fresh run supersedes earlier still-proposed options
        stale = await session.scalars(
            select(WcAction).where(
                WcAction.tenant_id == body.tenant_id, WcAction.status == "proposed"
            )
        )
        for row in stale:
            row.status = "stale"
        for option in body.options:
            session.add(
                WcAction(
                    id=uuid7(),
                    tenant_id=body.tenant_id,
                    run_id=body.run_id,
                    kind=option["kind"],
                    invoice_id=option["invoice_id"],
                    invoice_number=option["invoice_number"],
                    client=option["client"],
                    unlock_paise=option["unlock_paise"],
                    cost_paise=option["cost_paise"],
                    rank=option["rank"],
                    detail=option["detail"],
                )
            )
            created += 1
    return {"created": created, "existing": 0}


class CollectionsContext(BaseModel):
    overdue: list[dict[str, Any]]
    sender_name: str


@router.get("/collections/context", response_model=CollectionsContext)
async def collections_context(
    tenant_id: str, x_internal_token: str | None = Header(None)
) -> CollectionsContext:
    _check_token(x_internal_token)
    from datetime import UTC

    now = datetime.now(UTC)
    async with session_scope() as session:
        repo = BooksRepo(session)
        invoices = await repo.open_invoices(tenant_id)
        parties = {c.id: c for c in await repo.counterparties(tenant_id)}
        from app.db.repositories import TenantRepo

        tenant = await TenantRepo(session).by_id(tenant_id)
    overdue = []
    for inv in invoices:
        if inv.due_date >= now:
            continue
        client = parties.get(inv.counterparty_id)
        if client is None:
            continue
        overdue.append(
            {
                "invoice": {
                    "id": inv.id,
                    "number": inv.number,
                    "amount_paise": inv.amount_paise,
                    "due_date": inv.due_date.isoformat(),
                },
                "client": {
                    "id": client.id,
                    "name": client.name,
                    "emails": (client.contacts or {}).get("emails", []),
                },
            }
        )
    sender = f"Accounts, {tenant.name}" if tenant else "Accounts"
    return CollectionsContext(overdue=overdue, sender_name=sender)


class EmailQueueRequest(BaseModel):
    tenant_id: str
    run_id: str
    drafts: list[dict[str, Any]]


class EmailQueueOut(BaseModel):
    queued: int
    duplicates: int


@router.post("/collections/queue", response_model=EmailQueueOut)
async def queue_email_drafts(
    body: EmailQueueRequest, x_internal_token: str | None = Header(None)
) -> EmailQueueOut:
    _check_token(x_internal_token)
    from sqlalchemy import select

    from app.db.models import Approval
    from app.services.approvals import queue_approval

    queued = 0
    async with session_scope() as session:
        pending = await session.scalars(
            select(Approval).where(
                Approval.tenant_id == body.tenant_id,
                Approval.action_kind == "send_email",
                Approval.status == "pending",
            )
        )
        pending_invoices = {a.action_payload.get("invoice_id") for a in pending}
        # cooldown: an invoice chased in the last 7 days isn't chased again
        from datetime import UTC, timedelta

        from app.db.models import AuditLog

        cutoff = datetime.now(UTC) - timedelta(days=7)
        recently_sent = await session.scalars(
            select(AuditLog).where(
                AuditLog.tenant_id == body.tenant_id,
                AuditLog.action == "email.sent",
                AuditLog.created_at > cutoff,
            )
        )
        cooled_down = {r.entity_ref.removeprefix("invoice:") for r in recently_sent}
        for draft in body.drafts:
            if draft.get("invoice_id") in pending_invoices | cooled_down:
                continue
            await queue_approval(
                session,
                tenant_id=body.tenant_id,
                action_kind="send_email",
                action_payload=draft,
                requested_by={"kind": "agent", "run_id": body.run_id},
                policy_verdicts={
                    "rule": "external communication is always human-gated (P2)",
                    "tone": draft.get("tone"),
                    "days_overdue": draft.get("days_overdue"),
                },
            )
            queued += 1
    return EmailQueueOut(queued=queued, duplicates=len(body.drafts) - queued)


class CommitRequest(BaseModel):
    tenant_id: str
    run_id: str
    proposals: list[dict[str, Any]]


class CommitOut(BaseModel):
    results: list[dict[str, Any]]
    committed: int
    queued: int


@router.post("/recon/commit", response_model=CommitOut)
async def commit_matches(
    body: CommitRequest, x_internal_token: str | None = Header(None)
) -> CommitOut:
    _check_token(x_internal_token)
    results = []
    async with session_scope() as session:
        for proposal in body.proposals:
            results.append(
                await route_proposal(
                    session, tenant_id=body.tenant_id, run_id=body.run_id, proposal=proposal
                )
            )
        source_run = await RunRepo(session).by_id(body.run_id, body.tenant_id)
    committed = sum(1 for r in results if r["committed"])
    if committed and source_run is not None:
        # ledger changed — keep the forecast promise ("recomputed on ledger events")
        await trigger_forecast_recompute(
            tenant_id=body.tenant_id, requested_by=source_run.requested_by
        )
    return CommitOut(
        results=results,
        committed=committed,
        queued=sum(1 for r in results if r.get("queued")),
    )


# ---- month_end_close graph (F2 evidence run) --------------------------------


class CloseContextOut(BaseModel):
    period: str
    checklist: dict[str, Any]


@router.get("/close/context", response_model=CloseContextOut)
async def close_context(
    tenant_id: str, x_internal_token: str | None = Header(None)
) -> CloseContextOut:
    _check_token(x_internal_token)
    from datetime import UTC, datetime

    from app.config import get_settings
    from app.services.close import build_checklist

    now = datetime.now(UTC)
    async with session_scope() as session:
        checklist = await build_checklist(
            session,
            tenant_id=tenant_id,
            now=now,
            bank_rate_bps=get_settings().statutory_bank_rate_bps,
        )
    return CloseContextOut(period=now.strftime("%Y-%m"), checklist=checklist)


class CloseRunPersist(BaseModel):
    tenant_id: str
    run_id: str
    period: str
    checklist: dict[str, Any]


@router.post("/close/run")
async def persist_close_run(
    body: CloseRunPersist, x_internal_token: str | None = Header(None)
) -> dict[str, Any]:
    """Audit the evidence run. Never a sign-off — that stays a human
    maker-checker act on POST /api/v1/close/signoff."""
    _check_token(x_internal_token)
    from app.services.audit import write_audit

    async with session_scope() as session:
        await write_audit(
            session,
            tenant_id=body.tenant_id,
            actor={"kind": "agent", "run_id": body.run_id},
            action="close.checklist_run",
            entity_ref=f"close:{body.period}",
            payload={
                "period": body.period,
                "ready": body.checklist.get("ready"),
                "blockers": body.checklist.get("blockers"),
                "warnings": body.checklist.get("warnings"),
                "audit_head": body.checklist.get("audit_head"),
                "checks": [
                    {"id": c.get("id"), "ok": c.get("ok"), "value": c.get("value")}
                    for c in body.checklist.get("checks", [])
                ],
            },
        )
    return {
        "ready": body.checklist.get("ready"),
        "blockers": body.checklist.get("blockers", []),
        "warnings": body.checklist.get("warnings", []),
    }
