"""Collections graph — the empty-work guard, end to end.

Not a test of intelligence: a test that a clean ledger costs no memory queries
and reports itself as clean rather than as a run that produced nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from findesk_agents.backend_client import BackendClient
from findesk_agents.graphs.collections import graph as collections_graph
from findesk_agents.graphs.collections.state import CollectionsState
from findesk_agents.memoryclient import MemoryClient


class FakeEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    async def step(self, name: str, status: str, step_id: str, **detail: Any) -> None:
        self.events.append((name, status, detail))

    async def done(self, status: str, summary: str = "") -> None:
        self.events.append(("<run>", status, {"summary": summary}))

    def names(self) -> list[str]:
        return [n for n, s, _ in self.events if s == "started"]


class FakeBackend(BackendClient):
    def __init__(self, overdue: list[dict[str, Any]]) -> None:
        self._overdue = overdue
        self.queue_calls = 0

    async def collections_context(self, tenant_id: str) -> dict[str, Any]:
        return {"overdue": self._overdue, "sender_name": "Accounts, Test Co"}

    async def queue_email_approvals(self, tenant_id, run_id, drafts):
        self.queue_calls += 1
        return {"queued": len(drafts), "duplicates": 0}


class FakeMemory(MemoryClient):
    def __init__(self) -> None:
        self.recall_calls = 0

    async def recall_many(self, *, tenant_id, queries):
        self.recall_calls += 1
        return {}

    async def remember(self, **kw):
        return True


def _overdue_item():
    due = datetime.now(UTC) - timedelta(days=20)
    return {
        "invoice": {
            "id": "inv-1",
            "number": "INV-1001",
            "amount_paise": 5_000_000,
            "due_date": due.isoformat(),
        },
        "client": {"id": "cp-1", "name": "Acme Corp", "emails": ["ap@acme.test"]},
    }


async def _run(backend: FakeBackend, memory: FakeMemory, emitter: FakeEmitter):
    return await collections_graph.run(
        CollectionsState(
            tenant_id="t1", run_id="r1", emitter=emitter, backend=backend, memory=memory
        )
    )


async def test_clean_ledger_short_circuits_before_recall():
    backend, memory, emitter = FakeBackend([]), FakeMemory(), FakeEmitter()
    final = await _run(backend, memory, emitter)

    assert "nothing_due" in emitter.names()
    assert "draft" not in emitter.names()
    assert memory.recall_calls == 0, "no clients to ask about — skip the fan-out"
    assert backend.queue_calls == 0
    assert final.queued == 0
    assert final.summary == "No overdue invoices — nothing to chase."


async def test_overdue_invoice_takes_the_drafting_path():
    backend, memory, emitter = FakeBackend([_overdue_item()]), FakeMemory(), FakeEmitter()
    final = await _run(backend, memory, emitter)

    assert "draft" in emitter.names() and "queue_approvals" in emitter.names()
    assert "nothing_due" not in emitter.names()
    assert memory.recall_calls == 1, "recall-before-reason still runs on the real path"
    assert final.queued == 1
    assert "1 chaser drafts awaiting approval" in final.summary


def test_graph_branches_after_fetch():
    g = collections_graph.build_graph().get_graph()
    targets = {e.target for e in g.edges if e.source == "fetch_overdue"}
    assert targets == {"draft", "nothing_due"}
