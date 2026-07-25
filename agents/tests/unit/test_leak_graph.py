"""LeakRadar graph — both branches plus the critic gate, end to end.

Real compiled LangGraph, fake clients, LLM stubbed off so the unit suite never
depends on a provider key being present or absent.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from findesk_agents.backend_client import BackendClient
from findesk_agents.graphs.subscription_scan import graph as leak_graph
from findesk_agents.graphs.subscription_scan import nodes as leak_nodes
from findesk_agents.graphs.subscription_scan.state import SubscriptionState
from findesk_agents.memoryclient import MemoryClient

NOW = datetime.now(UTC)


def _debits(narration, amounts, *, gap=30, category="software_cloud", day_offset=5):
    start = NOW - timedelta(days=gap * len(amounts) + day_offset)
    return [
        {
            "id": f"{narration[:4]}{i}",
            "value_date": (start + timedelta(days=gap * i)).isoformat(),
            "amount_paise": a,
            "narration": narration,
            "counterparty_hint": None,
            "category_code": category,
        }
        for i, a in enumerate(amounts)
    ]


class FakeEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    async def step(self, name, status, step_id, **detail):
        self.events.append((name, status, detail))

    async def done(self, status, summary=""):
        self.events.append(("<run>", status, {"summary": summary}))

    def names(self):
        return [n for n, s, _ in self.events if s == "started"]

    def detail(self, name):
        return next(d for n, s, d in self.events if n == name and s == "finished")


class FakeBackend(BackendClient):
    def __init__(self, debits, mode="business") -> None:
        self._debits, self._mode = debits, mode
        self.persisted: list[dict[str, Any]] = []

    async def leak_context(self, tenant_id):
        return {"debits": [dict(d) for d in self._debits], "mode": self._mode}

    async def persist_leaks(self, tenant_id, run_id, rows):
        self.persisted = rows
        return {"created": len(rows), "updated": 0}


class FakeMemory(MemoryClient):
    def __init__(self, usage=None) -> None:
        self._usage = usage or {}

    async def recall_many(self, *, tenant_id, queries):
        out = {}
        for key, _q in queries:
            slug = key.split(":", 1)[1]
            if slug in self._usage:
                out[key] = [{"content": self._usage[slug]}]
        return out

    async def remember(self, **kw):
        return True


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setattr(leak_nodes, "get_llm", lambda role: None)


async def _run(backend, memory=None):
    return await leak_graph.run(
        SubscriptionState(
            tenant_id="t1", run_id="r1", emitter=FakeEmitter(),
            backend=backend, memory=memory or FakeMemory(),
        )
    ), backend


async def test_a_book_with_recurring_vendors_scores_and_persists():
    debits = _debits("NOTION TEAM PLAN", [400000] * 3 + [460000] * 4)
    final, backend = await _run(FakeBackend(debits))

    assert backend.persisted, "rows must reach persistence"
    row = backend.persisted[0]
    assert row["cadence"] == "monthly"
    assert row["drift_kind"] == "price_increase"
    assert row["recoverable_paise_per_year"] == 60000 * 12
    assert "recoverable" in final.summary


async def test_no_recurring_vendors_short_circuits():
    """Two charges is not a series — do not run drift and scoring to render an
    empty table."""
    debits = _debits("ONE OFF CONSULTANT", [500000, 500000], gap=45)
    emitter = FakeEmitter()
    state = SubscriptionState(
        tenant_id="t1", run_id="r1", emitter=emitter,
        backend=FakeBackend(debits), memory=FakeMemory(),
    )
    final = await leak_graph.run(state)

    assert "nothing_recurring" in emitter.names()
    assert "score" not in emitter.names()
    assert "persist" not in emitter.names()
    assert "No recurring vendors" in final.summary


async def test_confirmed_unused_from_memory_unlocks_the_run_rate():
    """The confirmation loop is what licenses counting the whole cost."""
    debits = _debits("GOLD GYM ELITE", [299900] * 7, category="fitness")
    slug = "gold-gym-elite"
    _, backend = await _run(
        FakeBackend(debits, mode="personal"),
        FakeMemory({slug: "The user no longer uses this service."}),
    )
    row = next(r for r in backend.persisted if r["vendor_slug"] == slug)
    assert row["usage"] == "unused"
    assert row["recoverable_paise_per_year"] == 299900 * 12
    assert row["recommended_action"].startswith("Cancel")


async def test_excluded_categories_reach_the_table_but_score_zero():
    """Payroll must be visible — so the user sees we know about it — and must
    never rank as a leak."""
    debits = _debits("SALARY PAYOUT STAFF BATCH", [42000000] * 7, category="payroll")
    _, backend = await _run(FakeBackend(debits))
    row = backend.persisted[0]
    assert row["leak_score"] == 0
    assert row["recoverable_paise_per_year"] == 0


async def test_critic_failure_fails_the_run_rather_than_persisting():
    """A table someone will cancel real services from must be self-consistent."""
    debits = _debits("NOTION TEAM PLAN", [400000] * 3 + [460000] * 4)
    backend = FakeBackend(debits)

    from findesk_agents.graphs.subscription_scan import graph as g

    original = leak_nodes.score  # captured BEFORE the swap, or this recurses

    async def broken_score(state):
        out = await original(state)
        out["rows"][0]["leak_score"] = 0  # money with a zero score
        return out

    try:
        leak_nodes.score = broken_score
        with pytest.raises(RuntimeError, match="leak critic rejected"):
            await g.build_graph().ainvoke(
                SubscriptionState(
                    tenant_id="t1", run_id="r1", emitter=FakeEmitter(),
                    backend=backend, memory=FakeMemory(),
                )
            )
    finally:
        leak_nodes.score = original
    assert not backend.persisted, "nothing may persist after a critic violation"


def test_graph_branches_after_recurrence():
    g = leak_graph.build_graph().get_graph()
    targets = {e.target for e in g.edges if e.source == "detect_recurrence"}
    assert targets == {"recall_usage", "nothing_recurring"}


async def test_llm_vendor_labels_reach_the_persisted_rows(monkeypatch):
    """Regression: canonicalize mutated state.debits in place without RETURNING
    it, so every rename was silently discarded — the step still reported
    "renamed: N" while the persisted rows kept their raw narrations. Asserting
    the step metric would not have caught this; only the output does."""

    class FakeLLM:
        model = "fake:test"

        async def complete_json(self, prompt, **kw):
            # only the canonicalization prompt carries "narrations"
            if '"narrations"' in prompt:
                return {"vendors": [{"slug": "notion-team-plan", "name": "Notion"}]}
            return None

    monkeypatch.setattr(leak_nodes, "get_llm", lambda role: FakeLLM())
    debits = _debits("NOTION TEAM PLAN", [400000] * 3 + [460000] * 4)
    _, backend = await _run(FakeBackend(debits))

    row = next(r for r in backend.persisted if r["vendor_slug"] == "notion-team-plan")
    assert row["vendor_label"] == "Notion", (
        f"got {row['vendor_label']!r} — the rename did not survive the graph"
    )


async def test_a_rename_for_an_unknown_slug_is_ignored():
    """A hallucinated slug must never introduce a vendor with no transactions."""

    class RogueLLM:
        model = "fake:rogue"

        async def complete_json(self, prompt, **kw):
            if '"narrations"' in prompt:
                return {"vendors": [{"slug": "vendor-that-does-not-exist", "name": "Ghost"}]}
            return None

    debits = _debits("NOTION TEAM PLAN", [400000] * 7)
    backend = FakeBackend(debits)
    state = SubscriptionState(
        tenant_id="t1", run_id="r1", emitter=FakeEmitter(),
        backend=backend, memory=FakeMemory(),
    )
    import findesk_agents.graphs.subscription_scan.nodes as n
    original = n.get_llm
    try:
        n.get_llm = lambda role: RogueLLM()
        await leak_graph.run(state)
    finally:
        n.get_llm = original

    labels = {r["vendor_label"] for r in backend.persisted}
    assert "Ghost" not in labels
    assert all(r["vendor_slug"] != "vendor-that-does-not-exist" for r in backend.persisted)
