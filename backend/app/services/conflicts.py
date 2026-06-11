"""A4 conflict cards: sync from Recall's conflict log, one-tap resolution.

Sync is lazy (on queue read): for each client counterparty we pull the
engine's conflict log and materialize unseen entries as cards, joining both
memory contents through the public API. Resolution keeps the winning belief,
deletes the losing memory (atomic, provenance-cascading), reinforces the
winner with a human-confirmed restatement, and audits the decision.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from findesk_shared import uuid7, vendor_scope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import memoryclient
from app.db.books_repo import BooksRepo
from app.db.models import Conflict
from app.services.audit import write_audit

# Only "flagged" keeps both beliefs alive (decisive resolutions tombstone the
# loser), so only flagged conflicts can become two-sided human cards.
SURFACED_RESOLUTIONS = {"flagged"}

# lazy-sync throttle: a busy dashboard polls /conflicts often — pulling the
# engine's log more than once per window per tenant is wasted fan-out
SYNC_WINDOW_SECONDS = 30.0
_last_sync: dict[str, float] = {}


def _claim_kind(content_a: str, content_b: str) -> str:
    text = f"{content_a} {content_b}".lower()
    if "tds" in text or "deduct" in text:
        return "deduction_pattern"
    if "category" in text or "expense" in text:
        return "vendor_category"
    if "pay" in text or "late" in text or "early" in text:
        return "payment_behavior"
    return "belief"


async def sync_conflicts(session: AsyncSession, tenant_id: str, *, force: bool = False) -> int:
    """Pull new engine conflicts into cards. Returns how many were created."""
    now = time.monotonic()
    if not force and now - _last_sync.get(tenant_id, 0.0) < SYNC_WINDOW_SECONDS:
        return 0
    _last_sync[tenant_id] = now

    repo = BooksRepo(session)
    known = {
        row.memory_conflict_id
        for row in await session.scalars(
            select(Conflict).where(Conflict.tenant_id == tenant_id)
        )
    }
    # scopes: client:<id> for counterparties + vendor:<slug> for debit vendors
    scopes: dict[str, str] = {}
    for party in await repo.counterparties(tenant_id):
        scopes[f"client:{party.id}"] = party.name
    for txn in await repo.debit_transactions(tenant_id):
        label = txn.counterparty_hint or txn.narration[:40]
        scopes[vendor_scope(txn.counterparty_hint, txn.narration)] = label

    # all engine-log reads run concurrently (semaphore-bounded in memoryclient)
    scope_items = list(scopes.items())
    conflict_lists = await asyncio.gather(
        *(
            memoryclient.list_conflicts(tenant_id=tenant_id, scope_key=scope_key)
            for scope_key, _ in scope_items
        )
    )

    created = 0
    for (scope_key, scope_label), engine_conflicts in zip(
        scope_items, conflict_lists, strict=True
    ):
        for c in engine_conflicts:
            cid = str(c["id"])
            if cid in known or c.get("resolution") not in SURFACED_RESOLUTIONS:
                continue
            units = await memoryclient.retrieve_units(
                tenant_id=tenant_id,
                scope_key=scope_key,
                query=c.get("resolved_belief") or "conflicting belief",
            )
            a_id, b_id = str(c.get("memory_a")), str(c.get("memory_b"))
            unit_a, unit_b = units.get(a_id), units.get(b_id)
            if unit_a is None or unit_b is None:
                continue  # one side already gone — nothing for a human to decide
            session.add(
                Conflict(
                    id=uuid7(),
                    tenant_id=tenant_id,
                    claim_kind=_claim_kind(unit_a["content"], unit_b["content"]),
                    scope_key=scope_key,
                    claim_a={
                        "memory_id": a_id,
                        "content": unit_a["content"],
                        "confidence": unit_a.get("confidence"),
                    },
                    claim_b={
                        "memory_id": b_id,
                        "content": unit_b["content"],
                        "confidence": unit_b.get("confidence"),
                    },
                    engine_view={
                        "semantic_distance": c.get("semantic_distance"),
                        "engine_resolution": c.get("resolution"),
                        "engine_rationale": c.get("rationale"),
                        "counterparty": scope_label,
                    },
                    memory_conflict_id=cid,
                )
            )
            created += 1
    return created


async def list_open_conflicts(session: AsyncSession, tenant_id: str) -> list[Conflict]:
    return list(
        await session.scalars(
            select(Conflict)
            .where(Conflict.tenant_id == tenant_id, Conflict.status == "open")
            .order_by(Conflict.created_at.desc())
        )
    )


async def resolve_conflict(
    session: AsyncSession,
    *,
    tenant_id: str,
    conflict_id: str,
    winner: str,  # "a" | "b"
    resolver_id: str,
    rationale: str | None = None,
) -> dict[str, Any]:
    conflict = await session.scalar(
        select(Conflict).where(Conflict.id == conflict_id, Conflict.tenant_id == tenant_id)
    )
    if conflict is None:
        return {"ok": False, "reason": "not found"}
    if conflict.status != "open":
        return {"ok": False, "reason": f"already {conflict.status}"}

    keep = conflict.claim_a if winner == "a" else conflict.claim_b
    drop = conflict.claim_b if winner == "a" else conflict.claim_a

    deleted = await memoryclient.delete_memory(drop["memory_id"])
    # Reinforce the winner via retrieval — the engine boosts strength on every
    # hit. (Never re-ingest a restatement: a near-duplicate belief would be
    # flagged as a new conflict against itself.)
    retrieved = await memoryclient.retrieve_units(
        tenant_id=tenant_id, scope_key=conflict.scope_key, query=keep["content"]
    )
    reinforced = keep["memory_id"] in retrieved

    conflict.status = "resolved"
    conflict.resolver_id = resolver_id
    conflict.resolution = {
        "winner": winner,
        "kept": keep["content"],
        "dropped": drop["content"],
        "loser_deleted": deleted,
        "winner_reinforced": reinforced,
        "rationale": rationale,
    }
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor={"kind": "user", "id": resolver_id},
        action="conflict.resolved",
        entity_ref=f"conflict:{conflict.id}",
        payload=conflict.resolution | {"memory_conflict_id": conflict.memory_conflict_id},
    )
    return {"ok": True, "kept": keep["content"], "loser_deleted": deleted}
