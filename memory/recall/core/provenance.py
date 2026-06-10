"""Provenance service — the epistemic history of every belief.

Wraps :class:`recall.db.neo4j_store.ProvenanceStore` with engine-level helpers:
recording direct statements / corroborations / contradictions, linking conflict
resolutions, and rendering a stored evidence chain into a plain-language
explanation for the ``GET /memory/{id}/why`` endpoint.

Writes are best-effort: a provenance failure must never block a memory write.
The graph is reconciled separately (see docs/adr) rather than wrapped in the
Postgres transaction.
"""

from __future__ import annotations

import uuid

from recall.db.neo4j_store import EvidenceNode, ProvenanceStore
from recall.logging import get_logger

log = get_logger(__name__)


class ProvenanceService:
    def __init__(self, store: ProvenanceStore | None = None) -> None:
        self._store = store or ProvenanceStore()

    async def record_direct(
        self, memory_id: uuid.UUID, *, session_id: str, confidence: float, note: str
    ) -> None:
        await self._safe(
            self._store.upsert_belief(str(memory_id), confidence, "active")
        )
        await self._safe(
            self._store.add_evidence(
                str(memory_id),
                EvidenceNode(str(uuid.uuid4()), "direct", session_id, 0.35, note),
                relation="SUPPORTS",
            )
        )

    async def record_corroboration(
        self, memory_id: uuid.UUID, *, session_id: str, weight: float, note: str
    ) -> None:
        await self._safe(
            self._store.add_evidence(
                str(memory_id),
                EvidenceNode(str(uuid.uuid4()), "corroboration", session_id, weight, note),
                relation="SUPPORTS",
            )
        )

    async def record_contradiction(
        self, memory_id: uuid.UUID, *, session_id: str, weight: float, note: str
    ) -> None:
        await self._safe(
            self._store.add_evidence(
                str(memory_id),
                EvidenceNode(str(uuid.uuid4()), "contradiction", session_id, -abs(weight), note),
                relation="CONTRADICTS",
            )
        )

    async def link_resolution(
        self, new_memory_id: uuid.UUID, source_ids: list[uuid.UUID]
    ) -> None:
        await self._safe(
            self._store.link_resolution(str(new_memory_id), [str(s) for s in source_ids])
        )

    async def explain(self, memory_id: uuid.UUID) -> dict:
        """Return the raw chain plus a rendered plain-language explanation."""
        chain = await self._store.get_chain(str(memory_id))
        chain["explanation"] = self._render(chain)
        return chain

    async def cascade_delete(self, memory_id: uuid.UUID) -> int:
        return await self._store.cascade_delete(str(memory_id))

    @staticmethod
    def _render(chain: dict) -> str:
        evidence = chain.get("evidence", [])
        if not evidence:
            return "No recorded evidence for this belief."
        lines = [f"This belief is held with confidence {chain.get('confidence')}. Evidence:"]
        for e in evidence:
            sign = "+" if e.get("weight", 0) >= 0 else ""
            lines.append(
                f"  - session {e.get('session_id')}: {e.get('type')} "
                f"[{sign}{e.get('weight')}] {e.get('note', '')}".rstrip()
            )
        resolved = chain.get("resolved_from") or []
        if resolved:
            lines.append(f"  - resolved from prior beliefs: {', '.join(resolved)}")
        return "\n".join(lines)

    @staticmethod
    async def _safe(coro) -> None:
        try:
            await coro
        except Exception as exc:  # noqa: BLE001 - provenance must not block writes
            log.warning("provenance.write_failed", error=str(exc))
