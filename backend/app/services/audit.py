"""Hash-chained audit writer — every consequential mutation goes through here.

Chain: row_hash = sha256(prev_hash ‖ canonical_payload). Verification walks the
chain per tenant; a broken link means tampering (alerting in Phase 5).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.books_repo import BooksRepo
from app.db.models import AuditLog


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


async def write_audit(
    session: AsyncSession,
    *,
    tenant_id: str,
    actor: dict[str, Any],
    action: str,
    entity_ref: str,
    payload: dict[str, Any],
) -> AuditLog:
    repo = BooksRepo(session)
    prev_hash = await repo.last_audit_hash(tenant_id)
    body = _canonical({"actor": actor, "action": action, "entity_ref": entity_ref, **payload})
    row_hash = hashlib.sha256(f"{prev_hash}|{body}".encode()).hexdigest()
    entry = AuditLog(
        tenant_id=tenant_id,
        actor=actor,
        action=action,
        entity_ref=entity_ref,
        payload=payload,
        prev_hash=prev_hash,
        row_hash=row_hash,
    )
    await repo.add_audit(entry)
    return entry


async def verify_chain(session: AsyncSession, tenant_id: str) -> dict[str, Any]:
    """Walk the tenant's audit chain and recompute every link. Deterministic.

    Returns {valid, entries, head_hash, broken_at?}: a broken link names the
    first row whose recomputed hash (or prev linkage) disagrees with what is
    stored — tamper-evidence a lender or CA can check live, not a promise.
    """
    from sqlalchemy import select

    rows = list(
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        )
    )
    prev = "genesis"
    for index, row in enumerate(rows):
        body = _canonical(
            {"actor": row.actor, "action": row.action, "entity_ref": row.entity_ref, **row.payload}
        )
        expected = hashlib.sha256(f"{prev}|{body}".encode()).hexdigest()
        if row.prev_hash != prev or row.row_hash != expected:
            return {
                "valid": False,
                "entries": len(rows),
                "broken_at": {"index": index, "id": row.id, "action": row.action},
                "head_hash": rows[-1].row_hash if rows else "genesis",
            }
        prev = row.row_hash
    return {"valid": True, "entries": len(rows), "head_hash": prev}
