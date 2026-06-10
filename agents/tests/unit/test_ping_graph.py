"""Ping graph unit tests — fake emitter, no Redis, no LLM."""

from typing import Any

from findesk_agents.graphs.ping import graph as ping_graph
from findesk_agents.graphs.ping.state import PingState


class FakeEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def step(self, name: str, status: str, step_id: str, **detail: Any) -> None:
        self.events.append(("step", {"name": name, "status": status, "step_id": step_id, **detail}))

    async def done(self, status: str, summary: str = "") -> None:
        self.events.append(("done", {"status": status, "summary": summary}))


async def test_ping_graph_runs_plan_execute_critic():
    emitter = FakeEmitter()
    state = PingState(tenant_id="t1", run_id="r1", emitter=emitter)
    final = await ping_graph.run(state)

    assert final.plan == ["check_pulse", "report"]
    assert final.executed == final.plan
    assert "pong" in final.summary

    names = [e[1]["name"] for e in emitter.events if e[0] == "step"]
    assert names[0] == "plan"
    assert names[-1] == "critic"
    # every step that started also finished
    started = {e[1]["step_id"] for e in emitter.events if e[1].get("status") == "started"}
    finished = {e[1]["step_id"] for e in emitter.events if e[1].get("status") == "finished"}
    assert started == finished


async def test_critic_flags_mismatch():
    emitter = FakeEmitter()
    state = PingState(tenant_id="t1", run_id="r1", emitter=emitter, plan=["a"], executed=["b"])
    from findesk_agents.graphs.ping.nodes import critic

    result = await critic(state)
    assert "mismatch" in result["summary"]
