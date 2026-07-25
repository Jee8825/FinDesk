"""Collections graph wiring — wiring only, logic in nodes.py/drafting.py."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from findesk_agents.graphs.collections import nodes
from findesk_agents.graphs.collections.state import CollectionsState


def build_graph():
    g = StateGraph(CollectionsState)
    g.add_node("fetch_overdue", nodes.fetch_overdue)
    g.add_node("draft", nodes.draft)
    g.add_node("queue_approvals", nodes.queue_for_approval)
    g.add_node("nothing_due", nodes.nothing_due)
    g.add_edge(START, "fetch_overdue")
    g.add_conditional_edges(
        "fetch_overdue",
        nodes.route_after_fetch,
        {"draft": "draft", "nothing_due": "nothing_due"},
    )
    g.add_edge("draft", "queue_approvals")
    g.add_edge("queue_approvals", END)
    g.add_edge("nothing_due", END)
    return g.compile()


async def run(state: CollectionsState) -> CollectionsState:
    result = await build_graph().ainvoke(state)
    return CollectionsState.model_validate(result)
