"""Why? v0 — the evidence trail behind a match/document, from the audit chain.

Composes with Recall's why-chain in Phase 2+; today it returns the app-side
provenance: who/what acted on the entity, in order, hash-chained.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.deps import Auth
from app.db import session_scope
from app.db.books_repo import BooksRepo

router = APIRouter(tags=["why"])

KNOWN_KINDS = {"match", "document", "ledger_entry", "invoice", "bank_transaction"}


class WhyEvent(BaseModel):
    at: str
    actor: dict[str, Any]
    action: str
    payload: dict[str, Any]
    row_hash: str


class WhyOut(BaseModel):
    entity_ref: str
    events: list[WhyEvent]


@router.get("/why/{entity_type}/{entity_id}", response_model=WhyOut)
async def why(entity_type: str, entity_id: str, auth: Auth) -> WhyOut:
    entity_ref = f"{entity_type}:{entity_id}"
    async with session_scope() as session:
        rows = await BooksRepo(session).audit_for_entity(auth.tenant_id, entity_ref)
    return WhyOut(
        entity_ref=entity_ref,
        events=[
            WhyEvent(
                at=r.created_at.isoformat(),
                actor=r.actor,
                action=r.action,
                payload=r.payload,
                row_hash=r.row_hash,
            )
            for r in rows
        ],
    )
