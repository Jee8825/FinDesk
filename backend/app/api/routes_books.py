"""Books surface: statement import, transactions feed, exceptions queue."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, status
from findesk_shared import uuid7
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


@router.get("/books/exceptions", response_model=TxnPage)
async def list_exceptions(auth: Auth) -> TxnPage:
    async with session_scope() as session:
        repo = BooksRepo(session)
        txns = await repo.unmatched_transactions(auth.tenant_id)
        counts = await repo.transaction_counts(auth.tenant_id)
    return TxnPage(items=[_txn_out(t) for t in txns], next_cursor=None, counts=counts)
