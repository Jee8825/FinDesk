"""Reconciliation graph — both branches of the critic decision, end to end.

Runs the real compiled LangGraph with fake clients. The LLM is stubbed off in
every test: a unit suite must never depend on a provider key being present (or
absent), and with keys in .env an unstubbed critic would make live calls.

Fakes subclass the concrete client types because ReconState validates them by
instance; switching those fields to Protocols would let these be plain stubs.
"""

from __future__ import annotations

from typing import Any

import pytest

from findesk_agents.backend_client import BackendClient
from findesk_agents.graphs.reconciliation import graph as recon_graph
from findesk_agents.graphs.reconciliation import nodes as recon_nodes
from findesk_agents.graphs.reconciliation.state import ReconState
from findesk_agents.memoryclient import MemoryClient

INVOICE = {
    "id": "inv-1",
    "number": "INV-1001",
    "amount_paise": 9_000_000,
    "issue_date": "2026-06-05",
    "due_date": "2026-07-05",
    "counterparty_id": "cp-1",
}
TXN = {
    "id": "txn-1",
    "amount_paise": 9_000_000,
    "value_date": "2026-07-10",
    "narration": "NEFT FROM ACME CORP INV-1001",
    "direction": "cr",
}


class FakeEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    async def step(self, name: str, status: str, step_id: str, **detail: Any) -> None:
        self.events.append((name, status, detail))

    async def done(self, status: str, summary: str = "") -> None:
        self.events.append(("<run>", status, {"summary": summary}))

    def names(self) -> list[str]:
        return [n for n, s, _ in self.events if s == "started"]

    def detail(self, name: str) -> dict[str, Any]:
        return next(d for n, s, d in self.events if n == name and s == "finished")


class FakeBackend(BackendClient):
    def __init__(self, *, unmatched=None, invoices=None) -> None:
        self.committed: list[dict[str, Any]] = []
        self._unmatched = [dict(TXN)] if unmatched is None else unmatched
        self._invoices = [dict(INVOICE)] if invoices is None else invoices

    async def recon_context(self, tenant_id: str) -> dict[str, Any]:
        return {
            "unmatched": self._unmatched,
            "open_invoices": self._invoices,
            "counterparties": [{"id": "cp-1", "name": "Acme Corp"}],
            "uncategorized_debits": [],
            "valid_category_codes": ["OFFICE"],
        }

    async def categorize(self, tenant_id, run_id, items):
        return {"applied": 0, "skipped": 0}

    async def commit(self, tenant_id, run_id, proposals):
        # mirrors services/recon.py: a critic-rejected proposal is never posted
        ok = [p for p in proposals if p.get("critic_verdict", {}).get("verdict") == "pass"]
        self.committed = ok
        return {
            "results": [{"committed": p in ok} for p in proposals],
            "committed": len(ok),
            "queued": 0,
        }


class FakeMemory(MemoryClient):
    def __init__(self) -> None:
        self.written: list[str] = []

    async def recall_many(self, *, tenant_id, queries):
        return {}

    async def remember(self, *, tenant_id, scope_key, run_id, content):
        self.written.append(content)
        return True


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Deterministic critic only — no network from a unit test, ever."""
    monkeypatch.setattr(recon_nodes, "get_critic_llm", lambda: None)


async def _run(backend: FakeBackend, memory: FakeMemory, emitter: FakeEmitter) -> ReconState:
    return await recon_graph.run(
        ReconState(
            tenant_id="t1",
            run_id="r1",
            document_id="",
            emitter=emitter,
            backend=backend,
            memory=memory,
        )
    )


async def test_passing_proposal_routes_to_commit_and_learn():
    backend, memory, emitter = FakeBackend(), FakeMemory(), FakeEmitter()
    final = await _run(backend, memory, emitter)

    assert "commit" in emitter.names() and "learn" in emitter.names()
    assert "escalate" not in emitter.names(), "commit path must not also escalate"
    assert emitter.detail("commit")["committed"] == 1
    assert "1 matched & posted" in final.summary
    assert memory.written, "learn writes a payment-timing observation on commit"


async def test_vetoed_proposal_routes_to_escalate_carrying_the_reason(monkeypatch):
    """The critic's finding must reach a human instead of being dropped."""

    def veto_all(proposals, open_invoices):
        return [
            {
                **p,
                "critic_verdict": {
                    "verdict": "fail",
                    "problems": ["narration names a different company"],
                    "checker": "deterministic-v0",
                },
            }
            for p in proposals
        ]

    monkeypatch.setattr(recon_nodes.matching, "critic_review", veto_all)
    backend, memory, emitter = FakeBackend(), FakeMemory(), FakeEmitter()
    final = await _run(backend, memory, emitter)

    assert "escalate" in emitter.names()
    assert "commit" not in emitter.names(), "nothing survived — do not call commit"
    assert "learn" not in emitter.names(), "nothing committed — nothing to learn"

    findings = emitter.detail("escalate")["findings"]
    assert len(findings) == 1
    assert findings[0]["invoice_number"] == "INV-1001"
    assert findings[0]["problems"] == ["narration names a different company"]
    assert "vetoed by the critic" in final.summary
    assert not backend.committed


async def test_no_candidates_escalates_with_an_honest_summary():
    backend = FakeBackend(unmatched=[], invoices=[])
    emitter = FakeEmitter()
    final = await _run(backend, FakeMemory(), emitter)

    assert "escalate" in emitter.names()
    assert emitter.detail("escalate")["vetoed"] == 0
    assert "no match candidates" in final.summary


def test_graph_topology_has_a_real_branch():
    g = recon_graph.build_graph().get_graph()
    targets = {e.target for e in g.edges if e.source == "critic"}
    assert targets == {"commit", "escalate"}, "critic must fan out, not fall through"
    assert any(getattr(e, "conditional", False) for e in g.edges), "branch must be conditional"
