"""Internal worker ↔ backend API (shared-token auth, never exposed publicly).

The agents layer has no DB access by rule; these endpoints are its only path
to app data. Every request is tenant-scoped explicitly — the worker passes the
tenant_id from the job envelope, and rows are filtered server-side regardless.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import anyio
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.db import session_scope
from app.db.books_repo import BooksRepo
from app.services.recon import route_proposal

router = APIRouter(prefix="/internal", tags=["internal"])


def _check_token(token: str | None) -> None:
    if token != get_settings().internal_api_token:
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
            "value_date",
            "amount_paise",
            "direction",
            "narration",
            "counterparty_hint",
            "dedupe_hash",
            "source",
        )
        rows = [
            {
                "id": uuid7(),
                "tenant_id": body.tenant_id,
                "bank_account_id": account.id,
                **{k: row[k] for k in columns if k in row},
                "value_date": datetime.fromisoformat(row["value_date"]),
            }
            for row in body.rows
        ]
        inserted, skipped = await repo.insert_transactions_deduped(rows)
    return TxnIngestOut(inserted=inserted, skipped=skipped)


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
            if item.get("category_code") not in valid:
                continue
            txn = await repo.transaction(item["bank_transaction_id"], body.tenant_id)
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
            if f["dedupe_key"] in known:
                continue
            session.add(
                Anomaly(
                    id=uuid7(),
                    tenant_id=body.tenant_id,
                    kind=f["kind"],
                    severity=f.get("severity", "medium"),
                    vendor_label=f["vendor_label"][:80],
                    evidence=f["evidence"],
                    recommended_action=f["recommended_action"][:300],
                    recoverable_paise=f.get("recoverable_paise"),
                    dedupe_key=f["dedupe_key"],
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
    return CommitOut(
        results=results,
        committed=sum(1 for r in results if r["committed"]),
        queued=sum(1 for r in results if r.get("queued")),
    )
