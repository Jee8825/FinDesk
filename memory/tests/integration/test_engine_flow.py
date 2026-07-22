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


@pytest.mark.asyncio
async def test_corroboration_count_accumulates_with_diminishing_returns(schema):
    """Repeated corroboration must raise confidence by *less* each time, which
    only works if corroboration_count carries forward across resolutions."""
    from recall.core import repository
    from recall.db import session_scope

    llm = FakeLLM()
    engine = _engine(llm)
    ts = "User primary backend language is TypeScript"

    # Initial belief (low confidence so increments don't clamp at 1.0).
    llm.queue_facts([ExtractedFact(content="User primary backend language is Python",
                                   tier="semantic", confidence=0.5, cluster="coding-preferences")])
    await engine.ingest(IngestRequest(user_id="u3", session_id="s1",
                                      content="python", scope="private"))

    # First corroboration: the FakeLLM resolves every conflict to `ts`.
    llm.queue_facts([ExtractedFact(content=ts, tier="semantic", confidence=0.5,
                                   cluster="coding-preferences")])
    r2 = await engine.ingest(IngestRequest(user_id="u3", session_id="s2",
                                           content="typescript", scope="private"))
    async with session_scope() as s:
        u2 = await repository.get_memory(s, r2.units[0].id)
    assert u2.corroboration_count == 1
    delta_first = u2.confidence - 0.5

    # Second corroboration of the same belief.
    llm.queue_facts([ExtractedFact(content=ts, tier="semantic", confidence=0.5,
                                   cluster="coding-preferences")])
    r3 = await engine.ingest(IngestRequest(user_id="u3", session_id="s3",
                                           content="typescript", scope="private"))
    async with session_scope() as s:
        u3 = await repository.get_memory(s, r3.units[0].id)
    assert u3.corroboration_count == 2
    delta_second = u3.confidence - u2.confidence

    # The hallmark of diminishing returns: the second bump is smaller.
    assert 0 < delta_second < delta_first


@pytest.mark.asyncio
async def test_dormancy_drifts_confidence_down_on_consolidation(schema):
    """Beliefs the user hasn't recalled across several later sessions drift down."""
    from recall.core import repository
    from recall.db import session_scope

    llm = FakeLLM()
    engine = _engine(llm)

    # Three beliefs with disjoint vocabulary (no conflicts), each in its own
    # session so the dormancy counter sees later sessions for the oldest belief.
    llm.queue_facts([ExtractedFact(content="alpha apple", tier="semantic", confidence=0.6)])
    r1 = await engine.ingest(IngestRequest(user_id="u4", session_id="s1", content="alpha"))
    llm.queue_facts([ExtractedFact(content="bravo banana", tier="semantic", confidence=0.6)])
    await engine.ingest(IngestRequest(user_id="u4", session_id="s2", content="bravo"))
    llm.queue_facts([ExtractedFact(content="charlie cherry", tier="semantic", confidence=0.6)])
    await engine.ingest(IngestRequest(user_id="u4", session_id="s3", content="charlie"))

    report = await engine.consolidate("u4")
    assert report["dormant_drifted"] >= 1

    async with session_scope() as s:
        oldest = await repository.get_memory(s, r1.units[0].id)
    assert oldest.confidence < 0.6


@pytest.mark.asyncio
async def test_why_delete_promote_are_tenant_scoped(schema):
    """A memory UUID alone must not expose, delete, or re-scope across tenants."""
    from recall.core import repository
    from recall.core.scoping import ScopeError
    from recall.db import session_scope

    llm = FakeLLM()
    engine = _engine(llm)
    llm.queue_facts([ExtractedFact(content="Tenant one secret preference",
                                   tier="semantic", confidence=0.9)])
    r = await engine.ingest(IngestRequest(user_id="u5", session_id="s1",
                                          content="secret", tenant_id="t1"))
    mid = r.units[0].id

    # why: another tenant gets an empty chain; the owning tenant gets evidence.
    assert (await engine.why(mid, tenant_id="t2")).evidence == []
    assert (await engine.why(mid, tenant_id="t1")).evidence

    # promote: cross-tenant is denied.
    with pytest.raises(ScopeError):
        await engine.promote(mid, "private", None, tenant_id="t2")

    # delete: cross-tenant is a no-op; the row survives.
    deleted, _ = await engine.delete(mid, tenant_id="t2")
    assert deleted is False
    async with session_scope() as s:
        assert await repository.get_memory(s, mid) is not None

    # delete: the owning tenant succeeds.
    deleted, _ = await engine.delete(mid, tenant_id="t1")
    assert deleted is True
