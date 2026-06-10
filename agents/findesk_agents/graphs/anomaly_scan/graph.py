"""Anomaly-scan graph wiring — wiring only, logic in nodes.py/detection.py."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from findesk_agents.graphs.anomaly_scan import nodes
from findesk_agents.graphs.anomaly_scan.state import AnomalyState


def build_graph():
    g = StateGraph(AnomalyState)
    g.add_node("fetch", nodes.fetch)
    g.add_node("recall_baselines", nodes.recall_baselines)
    g.add_node("detect", nodes.detect)
    g.add_node("persist", nodes.persist)
    g.add_node("learn", nodes.learn)
    g.add_edge(START, "fetch")
    g.add_edge("fetch", "recall_baselines")
    g.add_edge("recall_baselines", "detect")
    g.add_edge("detect", "persist")
    g.add_edge("persist", "learn")
    g.add_edge("learn", END)
    return g.compile()


async def run(state: AnomalyState) -> AnomalyState:
    result = await build_graph().ainvoke(state)
    return AnomalyState.model_validate(result)
