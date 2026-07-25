"""LeakRadar graph wiring — wiring only, logic in nodes.py and the detectors."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from findesk_agents.graphs.subscription_scan import nodes
from findesk_agents.graphs.subscription_scan.state import SubscriptionState


def build_graph():
    g = StateGraph(SubscriptionState)
    g.add_node("fetch", nodes.fetch)
    g.add_node("canonicalize", nodes.canonicalize)
    g.add_node("detect_recurrence", nodes.detect_recurrence)
    g.add_node("recall_usage", nodes.recall_usage)
    g.add_node("score", nodes.score)
    g.add_node("narrate", nodes.narrate)
    g.add_node("critic", nodes.critic_review)
    g.add_node("persist", nodes.persist)
    g.add_node("nothing_recurring", nodes.nothing_recurring)

    g.add_edge(START, "fetch")
    g.add_edge("fetch", "canonicalize")
    g.add_edge("canonicalize", "detect_recurrence")
    # the decision: a book with no recurring vendor should not run drift and
    # scoring over an empty set just to render an empty table
    g.add_conditional_edges(
        "detect_recurrence",
        nodes.route_after_recurrence,
        {"score": "recall_usage", "nothing_recurring": "nothing_recurring"},
    )
    # recall-before-reason: the human's usage answers are the one leak signal
    # bank data cannot produce, and they must be in hand before scoring
    g.add_edge("recall_usage", "score")
    g.add_edge("score", "narrate")
    g.add_edge("narrate", "critic")
    g.add_edge("critic", "persist")
    g.add_edge("persist", END)
    g.add_edge("nothing_recurring", END)
    return g.compile()


async def run(state: SubscriptionState) -> SubscriptionState:
    result = await build_graph().ainvoke(state)
    return SubscriptionState.model_validate(result)
