"""Books surface: statement import, transactions feed, exceptions queue."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

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
    upload_dir = Path(settings.upload_dir) / auth.tenant_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_path = upload_dir / f"{doc_id}-{Path(file.filename or 'statement.csv').name}"
    storage_path.write_bytes(content)

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
async def list_exceptions(auth: Auth) -> TxnPage:
    async with session_scope() as session:
        repo = BooksRepo(session)
        txns = await repo.unmatched_transactions(auth.tenant_id)
        counts = await repo.transaction_counts(auth.tenant_id)
    return TxnPage(items=[_txn_out(t) for t in txns], next_cursor=None, counts=counts)
