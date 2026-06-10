"""Framework-agnostic memory helper that all adapters build on.

Wraps the Recall SDK client with the two operations every framework needs:
``remember`` (ingest an exchange) and ``recall`` (retrieve budget-packed
context). Concrete adapters (LangGraph, LangChain, AutoGen) are thin shims over
this class, so the integration logic lives in one tested place.
"""

from __future__ import annotations

from dataclasses import dataclass

from recall.core.types import RetrievedMemory, Scope
from recall.sdk import Recall


@dataclass
class RecallMemory:
    user_id: str
    session_id: str = "default"
    base_url: str = "http://localhost:8000"
    client: Recall | None = None
    token_budget: int = 1500
    scope: Scope = "private"
    team_id: str | None = None
    tenant_id: str = "default"

    def _client(self) -> Recall:
        if self.client is None:
            self.client = Recall(self.base_url)
        return self.client

    async def remember(self, content: str) -> int:
        """Ingest content; return how many memory units were extracted."""
        result = await self._client().ingest(
            user_id=self.user_id,
            session_id=self.session_id,
            content=content,
            scope=self.scope,
            team_id=self.team_id,
            tenant_id=self.tenant_id,
        )
        return len(result.units)

    async def recall(self, query: str, token_budget: int | None = None) -> list[RetrievedMemory]:
        result = await self._client().retrieve(
            user_id=self.user_id,
            query=query,
            token_budget=token_budget or self.token_budget,
            scope=self.scope if self.scope != "private" else None,
            team_id=self.team_id,
            session_id=self.session_id,
            tenant_id=self.tenant_id,
        )
        return result.memories

    async def recall_text(self, query: str, token_budget: int | None = None) -> str:
        """Recall and format memories as a context block for a system prompt."""
        memories = await self.recall(query, token_budget)
        return self.format_context(memories)

    @staticmethod
    def format_context(memories: list[RetrievedMemory]) -> str:
        if not memories:
            return ""
        lines = ["Relevant memories about the user:"]
        for m in memories:
            hedge = "" if m.confidence >= 0.6 else " (low confidence)"
            lines.append(f"- {m.content}{hedge}")
        return "\n".join(lines)

    async def aclose(self) -> None:
        if self.client is not None:
            await self.client.aclose()
