"""Integration tests: consolidation (procedural extraction), prefetch, scoping."""

from __future__ import annotations

import pytest
from recall.core import scoping
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
async def test_consolidation_extracts_procedural_workflow(schema):
    engine = _engine(FakeLLM())

    # Seed agent runs with a repeated 4-step workflow.
    from recall.db import session_scope
    from recall.db.models import AgentRun, ToolCall

    async with session_scope() as s:
        for _ in range(3):
            run = AgentRun(user_id="pu", status="done")
            s.add(run)
            await s.flush()
            for name in ["search", "open", "edit", "save"]:
                s.add(ToolCall(run_id=run.run_id, tool_name=name))

    report = await engine.consolidate("pu")
    assert report["procedural_created"] >= 1

    # A procedural memory now exists describing the workflow.
    res = await engine.retrieve(RetrieveRequest(
        user_id="pu", query="search open edit save workflow", token_budget=500))
    assert any("workflow" in m.content.lower() for m in res.memories)


@pytest.mark.asyncio
async def test_prefetch_then_retrieve_marks_cache_hit(schema):
    llm = FakeLLM()
    engine = _engine(llm)
    llm.queue_facts([ExtractedFact(content="User deploys on AWS with kubectl",
                                   tier="semantic", confidence=0.9, cluster="cloud-deployment")])
    await engine.ingest(IngestRequest(
        user_id="pf", session_id="s1", content="We deploy on AWS using kubectl."))

    # Warm the cache (FakeLLM.classify returns the first candidate cluster, which
    # is the user's own 'cloud-deployment').
    outcome = await engine.prefetch(
        user_id="pf", session_id="s1", recent_turns=["where do we deploy again?"])
    assert outcome.predicted_cluster == "cloud-deployment"
    assert outcome.staged >= 1

    res = await engine.retrieve(RetrieveRequest(
        user_id="pf", query="deployment target", token_budget=500, session_id="s1"))
    assert res.cache_hit is True


@pytest.mark.asyncio
async def test_promote_to_global_requires_orchestrator(schema):
    llm = FakeLLM()
    engine = _engine(llm)
    llm.queue_facts([ExtractedFact(content="User timezone is UTC+5:30",
                                   tier="semantic", confidence=0.95, cluster="personal-info")])
    r = await engine.ingest(IngestRequest(
        user_id="sc", session_id="s1", content="My timezone is IST."))
    mid = r.units[0].id

    with pytest.raises(scoping.ScopeError):
        await engine.promote(mid, "global", None, is_orchestrator=False)

    # Orchestrator may promote to global.
    await engine.promote(mid, "global", None, is_orchestrator=True)
