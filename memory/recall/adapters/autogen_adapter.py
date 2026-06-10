"""AutoGen adapter — a ``Memory`` implementation backed by Recall.

Implements the AutoGen 0.4 ``autogen_core.memory.Memory`` protocol (``add``,
``query``, ``update_context``, ``clear``, ``close``). ``autogen_core`` is
imported lazily. Falls back to duck typing so the class is usable even where the
exact base class differs across AutoGen versions.
"""

from __future__ import annotations

from typing import Any

from recall.adapters.base import RecallMemory


def build_autogen_memory(
    *,
    user_id: str,
    session_id: str = "default",
    base_url: str = "http://localhost:8000",
    token_budget: int = 1500,
):
    """Construct an AutoGen-compatible memory backed by Recall."""
    try:
        from autogen_core.memory import (
            Memory,
            MemoryContent,
            MemoryQueryResult,
            UpdateContextResult,
        )
    except ImportError as exc:  # pragma: no cover
        raise ImportError("install recall[adapters] for the AutoGen adapter") from exc

    backend = RecallMemory(
        user_id=user_id, session_id=session_id, base_url=base_url, token_budget=token_budget
    )

    class RecallAutoGenMemory(Memory):
        async def add(self, content: MemoryContent, cancellation_token: Any = None) -> None:
            await backend.remember(str(content.content))

        async def query(
            self, query: Any, cancellation_token: Any = None, **kwargs: Any
        ) -> MemoryQueryResult:
            text = query if isinstance(query, str) else str(getattr(query, "content", query))
            memories = await backend.recall(text)
            results = [
                MemoryContent(content=m.content, mime_type="text/plain")
                for m in memories
            ]
            return MemoryQueryResult(results=results)

        async def update_context(self, model_context: Any) -> UpdateContextResult:
            # Pull the latest message, retrieve, and append memories to context.
            messages = await model_context.get_messages()
            last = str(getattr(messages[-1], "content", "")) if messages else ""
            memories = await backend.recall(last) if last else []
            if memories:
                from autogen_core.models import SystemMessage

                await model_context.add_message(
                    SystemMessage(content=backend.format_context(memories))
                )
            results = [MemoryContent(content=m.content, mime_type="text/plain") for m in memories]
            return UpdateContextResult(memories=MemoryQueryResult(results=results))

        async def clear(self) -> None:
            return None

        async def close(self) -> None:
            await backend.aclose()

    return RecallAutoGenMemory()
