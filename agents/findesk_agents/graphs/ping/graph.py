"""Ping graph wiring — wiring only, logic lives in nodes.py."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from findesk_agents.graphs.ping import nodes
from findesk_agents.graphs.ping.state import PingState


def build_graph():
    g = StateGraph(PingState)
    g.add_node("plan", nodes.plan)
    g.add_node("execute", nodes.execute)
    g.add_node("critic", nodes.critic)
    g.add_edge(START, "plan")
    g.add_edge("plan", "execute")
    g.add_edge("execute", "critic")
    g.add_edge("critic", END)
    return g.compile()


async def run(state: PingState) -> PingState:
    result = await build_graph().ainvoke(state)
    return PingState.model_validate(result)
