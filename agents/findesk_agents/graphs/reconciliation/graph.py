"""Reconciliation graph wiring — wiring only, logic in nodes.py/matching.py."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from findesk_agents.graphs.reconciliation import nodes
from findesk_agents.graphs.reconciliation.state import ReconState


def build_graph():
    g = StateGraph(ReconState)
    g.add_node("fetch_and_parse", nodes.fetch_and_parse)
    g.add_node("ingest", nodes.ingest)
    g.add_node("match", nodes.match)
    g.add_node("critic", nodes.critic)
    g.add_node("commit", nodes.commit)
    g.add_node("learn", nodes.learn)
    g.add_edge(START, "fetch_and_parse")
    g.add_edge("fetch_and_parse", "ingest")
    g.add_edge("ingest", "match")
    g.add_edge("match", "critic")
    g.add_edge("critic", "commit")
    g.add_edge("commit", "learn")
    g.add_edge("learn", END)
    return g.compile()


async def run(state: ReconState) -> ReconState:
    result = await build_graph().ainvoke(state)
    return ReconState.model_validate(result)
