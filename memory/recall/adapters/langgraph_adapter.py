"""LangGraph adapter — drop-in memory nodes for a StateGraph.

LangGraph state is a dict (or TypedDict). These node factories return async
callables you can add to a graph: one injects retrieved context into the state
before the LLM node, the other persists the latest exchange after it. No hard
dependency on ``langgraph`` is required at import time — the nodes operate on
plain dict state, so they compose with any StateGraph.

Example::

    from recall.adapters.langgraph_adapter import recall_nodes
    retrieve_node, ingest_node = recall_nodes(user_id="u1", session_id="s1")
    graph.add_node("recall", retrieve_node)
    graph.add_node("remember", ingest_node)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from recall.adapters.base import RecallMemory

State = dict[str, Any]
Node = Callable[[State], Awaitable[State]]


def _last_user_text(state: State) -> str:
    """Extract the latest human message text from common LangGraph state shapes."""
    messages = state.get("messages") or []
    for msg in reversed(messages):
        # Support both dict messages and LangChain message objects.
        role = getattr(msg, "type", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role in ("human", "user"):
            return getattr(msg, "content", None) or msg.get("content", "")
    # Fall back to the last message of any kind.
    if messages:
        last = messages[-1]
        return getattr(last, "content", None) or (
            last.get("content", "") if isinstance(last, dict) else ""
        )
    return state.get("input", "")


def recall_nodes(
    *,
    user_id: str,
    session_id: str = "default",
    base_url: str = "http://localhost:8000",
    memory: RecallMemory | None = None,
    token_budget: int = 1500,
    context_key: str = "recall_context",
) -> tuple[Node, Node]:
    """Return ``(retrieve_node, ingest_node)`` bound to a user/session."""
    mem = memory or RecallMemory(
        user_id=user_id, session_id=session_id, base_url=base_url, token_budget=token_budget
    )

    async def retrieve_node(state: State) -> State:
        query = _last_user_text(state)
        state[context_key] = await mem.recall_text(query) if query else ""
        return state

    async def ingest_node(state: State) -> State:
        text = _last_user_text(state)
        if text:
            await mem.remember(text)
        return state

    return retrieve_node, ingest_node
