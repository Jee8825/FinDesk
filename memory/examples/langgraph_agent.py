"""Example: a LangGraph agent with Recall as its long-term memory.

Run the Recall stack first (`docker compose up`), then:

    pip install -e ".[adapters,openai]"
    python examples/langgraph_agent.py

The graph has two Recall nodes: ``recall`` injects relevant memories into state
before the model, and ``remember`` persists the new exchange afterwards. Recall
handles decay, conflict resolution, and provenance underneath — the agent code
stays trivial.
"""

from __future__ import annotations

import asyncio

from recall.adapters import recall_nodes


async def main() -> None:
    retrieve_node, ingest_node = recall_nodes(
        user_id="demo-user", session_id="example", base_url="http://localhost:8000"
    )

    # Minimal hand-rolled graph (swap for langgraph.StateGraph in a real app).
    async def model_node(state: dict) -> dict:
        context = state.get("recall_context", "")
        print("--- memories injected into the prompt ---")
        print(context or "(none yet)")
        # A real app would call the LLM here with `context` in the system prompt.
        state["messages"].append({"role": "assistant", "content": "Noted."})
        return state

    # Turn 1: teach the agent something.
    state = {"messages": [{"role": "user", "content": "I deploy our backend on AWS with kubectl."}]}
    state = await retrieve_node(state)
    state = await model_node(state)
    await ingest_node(state)

    # Turn 2: ask about it in a later session — Recall recalls it.
    state = {"messages": [{"role": "user", "content": "where do I deploy again?"}]}
    state = await retrieve_node(state)
    await model_node(state)


if __name__ == "__main__":
    asyncio.run(main())
