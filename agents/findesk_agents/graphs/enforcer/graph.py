"""Enforcer graph wiring — wiring only, logic in nodes.py/letters.py."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from findesk_agents.graphs.enforcer import nodes
from findesk_agents.graphs.enforcer.state import EnforcerState


def build_graph():
    g = StateGraph(EnforcerState)
    g.add_node("detect", nodes.detect)
    g.add_node("prepare", nodes.prepare)
    g.add_edge(START, "detect")
    g.add_edge("detect", "prepare")
    g.add_edge("prepare", END)
    return g.compile()


async def run(state: EnforcerState) -> EnforcerState:
    result = await build_graph().ainvoke(state)
    return EnforcerState.model_validate(result)
