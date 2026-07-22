"""Why? — the composed evidence trail: app audit chain + memory why-chain.

App side: who/what acted on the entity, in order, hash-chained. Memory side:
the beliefs (with provenance explanations) that informed the agent for this
entity's counterparty — retrieved live from Recall, omitted gracefully when
the memory service is down.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter
from findesk_shared import vendor_scope
from pydantic import BaseModel, Field

from app import memoryclient
from app.auth.deps import Auth
from app.db import session_scope
from app.db.books_repo import BooksRepo

router = APIRouter(tags=["why"])

KNOWN_KINDS = {"match", "document", "ledger_entry", "invoice", "bank_transaction"}

MEMORY_BELIEFS_LIMIT = 3


class WhyEvent(BaseModel):
    at: str
    actor: dict[str, Any]
    action: str
    payload: dict[str, Any]
    row_hash: str


class MemoryBelief(BaseModel):
    memory_id: str
    scope_key: str
    content: str
    confidence: float | None = None
    explanation: str = ""


class WhyOut(BaseModel):
    entity_ref: str
    events: list[WhyEvent]
    memory: list[MemoryBelief] = Field(default_factory=list)


@router.get("/why/{entity_type}/{entity_id}", response_model=WhyOut)
async def why(entity_type: str, entity_id: str, auth: Auth) -> WhyOut:
    entity_ref = f"{entity_type}:{entity_id}"
    scopes: list[tuple[str, str]] = []  # (scope_key, retrieval query)
    async with session_scope() as session:
        repo = BooksRepo(session)
        refs = [entity_ref]
        # A transaction's agent history is audited under its match ref(s):
        # expand so Why?(transaction) tells the whole story.
        if entity_type in ("transaction", "bank_transaction"):
            matches = await repo.matches_for_transaction(auth.tenant_id, entity_id)
            refs += [f"match:{m.id}" for m in matches]
            txn = await repo.transaction(entity_id, auth.tenant_id)
            if txn is not None:
                scopes.append(
                    (vendor_scope(txn.counterparty_hint, txn.narration), txn.narration)
                )
            for m in matches:
                if m.target_kind == "invoice":
                    inv = await repo.invoice(m.target_id, auth.tenant_id)
                    if inv is not None:
                        scopes.append(
                            (f"client:{inv.counterparty_id}", f"invoice {inv.number}")
                        )
        elif entity_type == "invoice":
            inv = await repo.invoice(entity_id, auth.tenant_id)
            if inv is not None:
                scopes.append((f"client:{inv.counterparty_id}", f"invoice {inv.number}"))
        rows = await repo.audit_for_entities(auth.tenant_id, refs)
    memory = await _memory_beliefs(auth.tenant_id, scopes)
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
        memory=memory,
    )


async def _memory_beliefs(
    tenant_id: str, scopes: list[tuple[str, str]]
) -> list[MemoryBelief]:
    """Top beliefs per scope with their provenance explanations, best-effort."""
    beliefs: list[MemoryBelief] = []
    seen: set[str] = set()
    for scope_key, query in scopes:
        units = await memoryclient.retrieve_units(
            tenant_id=tenant_id, scope_key=scope_key, query=query
        )
        for memory_id, unit in list(units.items())[:MEMORY_BELIEFS_LIMIT]:
            if memory_id in seen:
                continue
            seen.add(memory_id)
            beliefs.append(
                MemoryBelief(
                    memory_id=memory_id,
                    scope_key=scope_key,
                    content=str(unit.get("content", "")),
                    confidence=unit.get("confidence"),
                )
            )
    # provenance explanations in parallel (each is one Recall round-trip)
    chains = await asyncio.gather(
        *(memoryclient.why_chain(tenant_id=tenant_id, memory_id=b.memory_id) for b in beliefs)
    )
    for belief, chain in zip(beliefs, chains, strict=True):
        if chain:
            belief.explanation = str(chain.get("explanation", ""))
    return beliefs[:MEMORY_BELIEFS_LIMIT]
