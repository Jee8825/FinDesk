"""LangChain adapter — a ``BaseMemory`` backed by Recall.

``langchain-core`` is imported lazily inside :func:`build_recall_memory` so the
rest of Recall imports without LangChain installed. The returned object plugs
into LangChain chains expecting a memory with ``load_memory_variables`` /
``save_context`` (and their async variants).
"""

from __future__ import annotations

import asyncio
from typing import Any

from recall.adapters.base import RecallMemory


def build_recall_memory(
    *,
    user_id: str,
    session_id: str = "default",
    base_url: str = "http://localhost:8000",
    memory_key: str = "history",
    input_key: str = "input",
    token_budget: int = 1500,
):
    """Construct a LangChain ``BaseMemory`` subclass instance backed by Recall."""
    try:
        from langchain_core.memory import BaseMemory
    except ImportError as exc:  # pragma: no cover
        raise ImportError("install recall[adapters] for the LangChain adapter") from exc

    backend = RecallMemory(
        user_id=user_id, session_id=session_id, base_url=base_url, token_budget=token_budget
    )

    class RecallLangChainMemory(BaseMemory):
        # pydantic v2 model config from BaseMemory; declare fields as attrs.
        memory_variables_key: str = memory_key

        @property
        def memory_variables(self) -> list[str]:
            return [memory_key]

        def load_memory_variables(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return asyncio.get_event_loop().run_until_complete(
                self.aload_memory_variables(inputs)
            )

        async def aload_memory_variables(self, inputs: dict[str, Any]) -> dict[str, Any]:
            query = inputs.get(input_key, "")
            return {memory_key: await backend.recall_text(query)}

        def save_context(self, inputs: dict[str, Any], outputs: dict[str, Any]) -> None:
            asyncio.get_event_loop().run_until_complete(self.asave_context(inputs, outputs))

        async def asave_context(self, inputs: dict[str, Any], outputs: dict[str, Any]) -> None:
            user = inputs.get(input_key, "")
            ai = next(iter(outputs.values()), "") if outputs else ""
            exchange = f"User: {user}\nAssistant: {ai}".strip()
            if exchange:
                await backend.remember(exchange)

        def clear(self) -> None:  # Recall manages its own forgetting; no-op.
            return None

    return RecallLangChainMemory()
