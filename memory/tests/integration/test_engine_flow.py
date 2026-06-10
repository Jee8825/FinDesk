"""End-to-end engine flow against real Postgres (pgvector) + Neo4j.

Covers the thin path plus the epistemic layer: ingest -> conflict detection +
resolution -> provenance -> budget-packed retrieval -> why -> GDPR delete.
"""

from __future__ import annotations

import pytest
from recall.core.engine import RecallEngine
from recall.core.provenance import ProvenanceService
from recall.core.types import ExtractedFact, IngestRequest, RetrieveRequest

from tests.integration.fakes import FakeEmbedder, FakeLLM

pytestmark = pytest.mark.integration


def _engine(llm: FakeLLM) -> RecallEngine:
    from recall.config import get_settings

    settings = get_settings()
    return RecallEngine(
        llm=llm,
        embedder=FakeEmbedder(settings.embedding_dim),
        provenance=ProvenanceService(),
        settings=settings,
    )


@pytest.mark.asyncio
async def test_ingest_retrieve_conflict_why_delete(schema):
    llm = FakeLLM()
    engine = _engine(llm)

    # 1. Ingest an initial belief.
    llm.queue_facts([ExtractedFact(content="User primary backend language is Python",
                                   tier="semantic", confidence=0.9, cluster="coding-preferences")])
    r1 = await engine.ingest(IngestRequest(
        user_id="u1", session_id="s1", content="I mostly write Python on the backend.",
        scope="user-owned"))
    assert len(r1.units) == 1
    assert r1.conflicts_detected == 0

    # 2. Ingest a contradicting belief -> conflict detected + resolved.
    llm.queue_facts([ExtractedFact(content="User primary backend language is TypeScript",
                                   tier="semantic", confidence=0.85, cluster="coding-preferences")])
    r2 = await engine.ingest(IngestRequest(
        user_id="u1", session_id="s2", content="Actually we moved the backend to TypeScript.",
        scope="user-owned"))
    assert r2.conflicts_detected == 1
    surviving_id = r2.units[0].id

    # 3. The conflict was logged.
    conflicts = await engine.list_conflicts("u1")
    assert len(conflicts) == 1
    assert conflicts[0].resolution in ("auto_resolved", "merged", "flagged")

    # 4. Retrieval returns the surviving belief within the token budget.
    res = await engine.retrieve(RetrieveRequest(
        user_id="u1", query="what backend language does the user use", token_budget=500))
    assert res.tokens_used <= res.token_budget
    assert any("TypeScript" in m.content for m in res.memories)

    # 5. Provenance explains why the belief is held.
    why = await engine.why(surviving_id)
    assert why.explanation
    assert len(why.evidence) >= 1

    # 6. GDPR: user-owned listing then cascade delete.
    owned = await engine.list_user_owned("u1")
    assert any(u.id == surviving_id for u in owned)
    await engine.delete(surviving_id, cascade=True)
    why_after = await engine.why(surviving_id)
    assert why_after.evidence == []


@pytest.mark.asyncio
async def test_retrieval_reinforces_strength(schema):
    llm = FakeLLM()
    engine = _engine(llm)
    llm.queue_facts([ExtractedFact(content="User deploys services on AWS with kubectl",
                                   tier="semantic", confidence=0.9, cluster="cloud-deployment")])
    r = await engine.ingest(IngestRequest(
        user_id="u2", session_id="s1", content="We deploy on AWS using kubectl."))
    mid = r.units[0].id

    # Retrieve a few times; retrieval_count should climb (reinforcement path).
    for _ in range(3):
        await engine.retrieve(RetrieveRequest(
            user_id="u2", query="where does the user deploy", token_budget=500))

    from recall.core import repository
    from recall.db import session_scope

    async with session_scope() as s:
        unit = await repository.get_memory(s, mid)
        assert unit is not None
        assert unit.retrieval_count >= 1
