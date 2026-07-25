"""month_end_close graph wiring — wiring only, logic in nodes.py/critic.py."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from findesk_agents.graphs.month_end_close import nodes
from findesk_agents.graphs.month_end_close.state import CloseState


def build_graph():
    g = StateGraph(CloseState)
    g.add_node("fetch_checklist", nodes.fetch_checklist)
    g.add_node("critic", nodes.critic_review)
    g.add_node("persist", nodes.persist)
    g.add_edge(START, "fetch_checklist")
    g.add_edge("fetch_checklist", "critic")
    g.add_edge("critic", "persist")
    g.add_edge("persist", END)
    return g.compile()


async def run(state: CloseState) -> CloseState:
    result = await build_graph().ainvoke(state)
    return CloseState.model_validate(result)
