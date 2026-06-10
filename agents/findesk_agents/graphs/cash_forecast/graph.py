"""Cash-forecast graph wiring — wiring only, logic in nodes.py/engine.py."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from findesk_agents.graphs.cash_forecast import nodes
from findesk_agents.graphs.cash_forecast.state import ForecastState


def build_graph():
    g = StateGraph(ForecastState)
    g.add_node("fetch", nodes.fetch)
    g.add_node("recall_behavior", nodes.recall_behavior)
    g.add_node("project", nodes.projector)
    g.add_node("persist", nodes.persist)
    g.add_edge(START, "fetch")
    g.add_edge("fetch", "recall_behavior")
    g.add_edge("recall_behavior", "project")
    g.add_edge("project", "persist")
    g.add_edge("persist", END)
    return g.compile()


async def run(state: ForecastState) -> ForecastState:
    result = await build_graph().ainvoke(state)
    return ForecastState.model_validate(result)
