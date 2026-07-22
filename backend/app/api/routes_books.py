"""Books surface: statement import, transactions feed, exceptions queue."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, UploadFile, status
from findesk_shared import uuid7, vendor_scope
from pydantic import BaseModel

from app.auth.deps import Auth
from app.config import get_settings
from app.db import session_scope
from app.db.books_repo import BooksRepo
from app.db.models import AgentRun, Document
from app.db.repositories import RunRepo
from app.events.streams import enqueue_job
from app.services.audit import write_audit

router = APIRouter(tags=["books"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class ImportOut(BaseModel):
    document_id: str
    run_id: str


class TxnOut(BaseModel):
    id: str
    value_date: str
    amount_paise: int
    direction: str
    narration: str
    counterparty_hint: str | None
    match_status: str
    category_code: str | None = None
    category_source: str | None = None


class TxnPage(BaseModel):
    items: list[TxnOut]
    next_cursor: str | None
    counts: dict[str, int]


def _txn_out(t: Any) -> TxnOut:
    return TxnOut(
        id=t.id,
        value_date=t.value_date.date().isoformat(),
        amount_paise=t.amount_paise,
        direction=t.direction,
        narration=t.narration,
        counterparty_hint=t.counterparty_hint,
        match_status=t.match_status,
        category_code=t.category_code,
        category_source=t.category_source,
    )


@router.post("/books/imports", status_code=status.HTTP_202_ACCEPTED, response_model=ImportOut)
async def import_statement(file: UploadFile, auth: Auth) -> ImportOut:
    if auth.role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "viewers cannot import")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large")
    if not content.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "empty file")

    settings = get_settings()
    doc_id = uuid7()
    digest = hashlib.sha256(content).hexdigest()
    upload_dir = anyio.Path(settings.upload_dir) / auth.tenant_id
    storage_path = upload_dir / f"{doc_id}-{Path(file.filename or 'statement.csv').name}"
    # write bytes BEFORE the DB transaction (the worker reads this path the
    # moment the job lands) and non-blockingly; on failure → clean 507
    try:
        await upload_dir.mkdir(parents=True, exist_ok=True)
        await storage_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(
            status.HTTP_507_INSUFFICIENT_STORAGE, f"could not store upload: {exc}"
        ) from exc

    run = AgentRun(
        tenant_id=auth.tenant_id,
        graph="reconciliation",
        params={"document_id": doc_id},
        requested_by=auth.user_id,
    )
    async with session_scope() as session:
        await BooksRepo(session).add_document(
            Document(
                id=doc_id,
                tenant_id=auth.tenant_id,
                kind="bank_statement",
                filename=file.filename or "statement.csv",
                content_hash=digest,
                storage_path=str(storage_path),
                meta={"size": len(content)},
            )
        )
        await RunRepo(session).add(run)
        await write_audit(
            session,
            tenant_id=auth.tenant_id,
            actor={"kind": "user", "id": auth.user_id},
            action="document.upload",
            entity_ref=f"document:{doc_id}",
            payload={"filename": file.filename, "sha256": digest},
        )

    await enqueue_job(
        "job.reconciliation.requested@v1",
        auth.tenant_id,
        run.id,
        {"source": "user", "document_id": doc_id},
    )
    return ImportOut(document_id=doc_id, run_id=run.id)


class OnboardingOut(BaseModel):
    source_hint: str
    counterparties_created: int
    invoices_created: int
    invoices_skipped: int
    observations_seeded: int


@router.post(
    "/books/onboarding", status_code=status.HTTP_201_CREATED, response_model=OnboardingOut
)
async def onboard_invoices(file: UploadFile, auth: Auth) -> OnboardingOut:
    """A1 onboarding: import a Tally/Zoho invoice export.

    Creates counterparties + invoices (idempotent by name/number) and seeds
    paid history into memory as payment_behavior observations — so matching,
    chasing and forecasting are intelligent from day one.
    """
    if auth.role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "viewers cannot import")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large")
    from findesk_tools.bank_statements.schemas import ToolError
    from findesk_tools.ledger_import import parse_invoice_export

    try:
        result = parse_invoice_export(content.decode(errors="replace"))
    except ToolError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.reason) from exc

    from findesk_shared import format_inr
    from sqlalchemy import select

    from app import memoryclient
    from app.db.models import Counterparty, Invoice

    parties_created = 0
    created = 0
    skipped = 0
    observations: list[tuple[str, str]] = []  # (scope_key, content)

    async with session_scope() as session:
        repo = BooksRepo(session)
        parties = {c.name.lower(): c for c in await repo.counterparties(auth.tenant_id)}
        existing_numbers = {
            i.number
            for i in await session.scalars(
                select(Invoice).where(Invoice.tenant_id == auth.tenant_id)
            )
        }
        for inv in result.invoices:
            party = parties.get(inv.client_name.lower())
            if party is None:
                party = Counterparty(
                    id=uuid7(),
                    tenant_id=auth.tenant_id,
                    kind="client",
                    name=inv.client_name,
                    contacts={},
                )
                session.add(party)
                parties[inv.client_name.lower()] = party
                parties_created += 1
            if inv.number in existing_numbers:
                skipped += 1
                continue
            session.add(
                Invoice(
                    id=uuid7(),
                    tenant_id=auth.tenant_id,
                    counterparty_id=party.id,
                    number=inv.number,
                    issue_date=inv.issue_date,
                    due_date=inv.due_date,
                    acceptance_date=inv.issue_date,
                    amount_paise=inv.amount_paise,
                    status=inv.status,
                )
            )
            existing_numbers.add(inv.number)
            created += 1
            if inv.status == "paid" and inv.paid_date is not None:
                delta = (inv.paid_date.date() - inv.due_date.date()).days
                timing = f"{delta} days late" if delta > 0 else f"{-delta} days early"
                observations.append(
                    (
                        f"client:{party.id}",
                        f"Invoice {inv.number} ({format_inr(inv.amount_paise)}) was paid "
                        f"{timing} relative to its due date {inv.due_date.date().isoformat()}.",
                    )
                )
        await write_audit(
            session,
            tenant_id=auth.tenant_id,
            actor={"kind": "user", "id": auth.user_id},
            action="books.onboarded",
            entity_ref=f"tenant:{auth.tenant_id}",
            payload={
                "source_hint": result.source_hint,
                "filename": file.filename,
                "invoices_created": created,
                "counterparties_created": parties_created,
            },
        )

    seeded = 0
    for scope_key, text in observations:
        ok = await memoryclient.remember(
            tenant_id=auth.tenant_id,
            scope_key=scope_key,
            session_id="seed:onboarding",
            content=text,
        )
        seeded += 1 if ok else 0

    return OnboardingOut(
        source_hint=result.source_hint,
        counterparties_created=parties_created,
        invoices_created=created,
        invoices_skipped=skipped,
        observations_seeded=seeded,
    )


@router.get("/books/transactions", response_model=TxnPage)
async def list_transactions(
    auth: Auth, status_filter: str | None = None, cursor: str | None = None, limit: int = 50
) -> TxnPage:
    async with session_scope() as session:
        repo = BooksRepo(session)
        txns = await repo.transactions(
            auth.tenant_id, status=status_filter, limit=limit, cursor=cursor
        )
        counts = await repo.transaction_counts(auth.tenant_id)
    next_cursor = txns[-1].id if len(txns) == min(limit, 500) else None
    return TxnPage(items=[_txn_out(t) for t in txns], next_cursor=next_cursor, counts=counts)


class ChartAccountOut(BaseModel):
    code: str
    name: str
    type: str


@router.get("/books/chart-of-accounts", response_model=list[ChartAccountOut])
async def chart_of_accounts(auth: Auth) -> list[ChartAccountOut]:
    async with session_scope() as session:
        rows = await BooksRepo(session).chart_accounts(auth.tenant_id)
        return [ChartAccountOut(code=c.code, name=c.name, type=c.type) for c in rows]


class CategoryPatch(BaseModel):
    category_code: str


@router.patch("/books/transactions/{txn_id}/category")
async def correct_category(txn_id: str, body: CategoryPatch, auth: Auth) -> dict[str, Any]:
    if auth.role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "viewers cannot categorize")
    async with session_scope() as session:
        repo = BooksRepo(session)
        valid = {c.code for c in await repo.chart_accounts(auth.tenant_id)}
        if body.category_code not in valid:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unknown category code")
        txn = await repo.transaction(txn_id, auth.tenant_id)
        if txn is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "transaction not found")
        previous = txn.category_code
        await repo.set_category(
            txn_id,
            code=body.category_code,
            source="human",
            confidence=1.0,
            overwrite_human=True,
        )
        await write_audit(
            session,
            tenant_id=auth.tenant_id,
            actor={"kind": "user", "id": auth.user_id},
            action="transaction.category_corrected",
            entity_ref=f"bank_transaction:{txn_id}",
            payload={"from": previous, "to": body.category_code},
        )
        narration = txn.narration
        hint = txn.counterparty_hint

    # human corrections become vendor_category memory — this is how the agent
    # learns the tenant's taxonomy (crystallizes after repeated corroboration)
    from app import memoryclient

    await memoryclient.remember(
        tenant_id=auth.tenant_id,
        scope_key=vendor_scope(hint, narration),
        session_id=f"correction:{txn_id}",
        content=(
            f"Vendor '{hint or narration[:40]}' expenses are categorized as "
            f"{body.category_code} (set by human correction)."
        ),
    )
    return {"ok": True, "category_code": body.category_code}


@router.get("/books/exceptions", response_model=TxnPage)
async def list_exceptions(auth: Auth) -> TxnPage:
    async with session_scope() as session:
        repo = BooksRepo(session)
        txns = await repo.unmatched_transactions(auth.tenant_id)
        counts = await repo.transaction_counts(auth.tenant_id)
    return TxnPage(items=[_txn_out(t) for t in txns], next_cursor=None, counts=counts)


class TallySyncOut(BaseModel):
    mode: str  # fixture | live — demo data never masquerades as a live pull
    period: str
    invoices_created: int
    invoices_skipped: int
    bills_created: int
    bills_skipped: int
    parties_created: int
    unclassified_vendors: int


@router.post("/books/imports/tally", response_model=TallySyncOut)
async def import_from_tally(auth: Auth) -> TallySyncOut:
    """Pull outstanding receivables + payables through the Tally connector.

    Runs the real gateway protocol in both modes; "fixture" replays checked-in
    gateway XML when no TallyPrime is reachable (crucible C1 demo path).
    """
    if auth.role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "viewers cannot import")
    from datetime import UTC, datetime, timedelta

    from findesk_tools.tally import ToolError as TallyError

    from app.services.tally_sync import build_gateway, sync_books

    gateway, mode = build_gateway()
    to_date = datetime.now(UTC).date().isoformat()
    from_date = (datetime.now(UTC) - timedelta(days=120)).date().isoformat()
    try:
        # gateway transport is sync (stdlib) — keep the event loop free
        receivables = await anyio.to_thread.run_sync(
            lambda: gateway.list_invoices(from_date, to_date)
        )
        payables = await anyio.to_thread.run_sync(
            lambda: gateway.list_bills(from_date, to_date)
        )
    except TallyError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else 422
        raise HTTPException(code, f"tally gateway: {exc.reason}") from exc

    async with session_scope() as session:
        summary = await sync_books(
            session, auth.tenant_id, receivables=receivables, payables=payables
        )
        await write_audit(
            session,
            tenant_id=auth.tenant_id,
            actor={"kind": "user", "id": auth.user_id},
            action="books.tally_sync",
            entity_ref=f"tenant:{auth.tenant_id}",
            payload={"mode": mode, **{k: v for k, v in summary.items() if k != "fetched_at"}},
        )
    return TallySyncOut(mode=mode, period=f"{from_date}..{to_date}", **{
        k: v for k, v in summary.items() if k != "fetched_at"
    })
