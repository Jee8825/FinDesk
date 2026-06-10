"""Neo4j-backed provenance graph.

Each belief (a semantic memory unit) is a ``:Belief`` node keyed by its Postgres
``memory_id``. Evidence accreted across sessions attaches as ``:Evidence`` nodes
linked by ``:SUPPORTS`` / ``:CONTRADICTS``. Conflict resolutions link beliefs via
``:RESOLVED_FROM``. This is the epistemic history of *why* the agent believes
something — distinct from Cognee-style domain knowledge graphs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from recall.config import get_settings

_driver: AsyncDriver | None = None


def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        s = get_settings()
        _driver = AsyncGraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


CONSTRAINTS = [
    "CREATE CONSTRAINT belief_id IF NOT EXISTS "
    "FOR (b:Belief) REQUIRE b.memory_id IS UNIQUE",
    "CREATE CONSTRAINT evidence_id IF NOT EXISTS "
    "FOR (e:Evidence) REQUIRE e.evidence_id IS UNIQUE",
]


async def init_schema() -> None:
    """Create uniqueness constraints (idempotent). Called on startup."""
    driver = get_driver()
    async with driver.session() as session:
        for stmt in CONSTRAINTS:
            await session.run(stmt)


@dataclass
class EvidenceNode:
    evidence_id: str
    type: str  # direct | corroboration | contradiction | tool_pattern
    session_id: str
    weight: float
    note: str


class ProvenanceStore:
    """Thin async wrapper over the provenance graph operations."""

    def __init__(self, driver: AsyncDriver | None = None) -> None:
        self._driver = driver or get_driver()

    async def upsert_belief(self, memory_id: str, confidence: float, status: str) -> None:
        await self._run(
            "MERGE (b:Belief {memory_id: $mid}) "
            "SET b.confidence = $conf, b.status = $status",
            mid=memory_id, conf=confidence, status=status,
        )

    async def add_evidence(self, memory_id: str, ev: EvidenceNode, relation: str) -> None:
        """Attach an evidence node to a belief.

        ``relation`` is ``SUPPORTS`` or ``CONTRADICTS``.
        """
        await self._run(
            "MERGE (b:Belief {memory_id: $mid}) "
            "CREATE (e:Evidence {evidence_id: $eid, type: $etype, "
            "session_id: $sid, weight: $w, note: $note}) "
            f"CREATE (e)-[:{relation}]->(b)",
            mid=memory_id, eid=ev.evidence_id, etype=ev.type,
            sid=ev.session_id, w=ev.weight, note=ev.note,
        )

    async def link_resolution(self, new_memory_id: str, source_memory_ids: list[str]) -> None:
        """Record that ``new_memory_id`` was resolved from prior beliefs."""
        for src in source_memory_ids:
            await self._run(
                "MERGE (n:Belief {memory_id: $new}) "
                "MERGE (s:Belief {memory_id: $src}) "
                "MERGE (n)-[:RESOLVED_FROM]->(s)",
                new=new_memory_id, src=src,
            )

    async def get_chain(self, memory_id: str) -> dict[str, Any]:
        """Return the full evidence chain for a belief, for the ``why`` endpoint."""
        records = await self._fetch(
            "MATCH (b:Belief {memory_id: $mid}) "
            "OPTIONAL MATCH (e:Evidence)-[r]->(b) "
            "OPTIONAL MATCH (b)-[:RESOLVED_FROM]->(src:Belief) "
            "RETURN b.confidence AS confidence, b.status AS status, "
            "collect(DISTINCT {type: e.type, session_id: e.session_id, "
            "weight: e.weight, note: e.note, relation: type(r)}) AS evidence, "
            "collect(DISTINCT src.memory_id) AS resolved_from",
            mid=memory_id,
        )
        if not records:
            return {"memory_id": memory_id, "confidence": None, "evidence": [], "resolved_from": []}
        rec = records[0]
        evidence = [e for e in rec["evidence"] if e.get("type") is not None]
        return {
            "memory_id": memory_id,
            "confidence": rec["confidence"],
            "status": rec["status"],
            "evidence": evidence,
            "resolved_from": [r for r in rec["resolved_from"] if r is not None],
        }

    async def cascade_delete(self, memory_id: str) -> int:
        """Delete a belief and every evidence node derived from it (GDPR)."""
        records = await self._fetch(
            "MATCH (b:Belief {memory_id: $mid}) "
            "OPTIONAL MATCH (e:Evidence)-[]->(b) "
            "WITH b, collect(e) AS evs "
            "DETACH DELETE b "
            "FOREACH (e IN evs | DETACH DELETE e) "
            "RETURN size(evs) AS deleted_evidence",
            mid=memory_id,
        )
        return records[0]["deleted_evidence"] if records else 0

    async def _run(self, query: str, **params: Any) -> None:
        async with self._driver.session() as session:
            await session.run(query, **params)

    async def _fetch(self, query: str, **params: Any) -> list[dict[str, Any]]:
        async with self._driver.session() as session:
            result = await session.run(query, **params)
            return [dict(r) async for r in result]
