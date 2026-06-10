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
from app.services.recon import commit_proposal

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
    return ReconContext(
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


class CommitRequest(BaseModel):
    tenant_id: str
    run_id: str
    proposals: list[dict[str, Any]]


class CommitOut(BaseModel):
    results: list[dict[str, Any]]
    committed: int


@router.post("/recon/commit", response_model=CommitOut)
async def commit_matches(
    body: CommitRequest, x_internal_token: str | None = Header(None)
) -> CommitOut:
    _check_token(x_internal_token)
    results = []
    async with session_scope() as session:
        for proposal in body.proposals:
            results.append(
                await commit_proposal(
                    session, tenant_id=body.tenant_id, run_id=body.run_id, proposal=proposal
                )
            )
    return CommitOut(results=results, committed=sum(1 for r in results if r["committed"]))
