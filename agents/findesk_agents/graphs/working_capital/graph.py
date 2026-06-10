"""Working-capital graph wiring — wiring only, logic in nodes.py/options.py."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from findesk_agents.graphs.working_capital import nodes
from findesk_agents.graphs.working_capital.state import WorkingCapitalState


def build_graph():
    g = StateGraph(WorkingCapitalState)
    g.add_node("fetch", nodes.fetch)
    g.add_node("recall_behavior", nodes.recall_behavior)
    g.add_node("build_options", nodes.build)
    g.add_node("persist", nodes.persist)
    g.add_edge(START, "fetch")
    g.add_edge("fetch", "recall_behavior")
    g.add_edge("recall_behavior", "build_options")
    g.add_edge("build_options", "persist")
    g.add_edge("persist", END)
    return g.compile()


async def run(state: WorkingCapitalState) -> WorkingCapitalState:
    result = await build_graph().ainvoke(state)
    return WorkingCapitalState.model_validate(result)
