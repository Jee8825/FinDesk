"""Recall memory helper for graphs — identity mapping per contracts/memory.md.

Degrades gracefully: if the memory service is down or slow, graphs proceed and
record that memory was skipped (Phase-1 posture; the wiring — tenancy, scope
keys, run-id stamping, budgets — is exercised whenever the stack is up).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from findesk_agents.config import get_settings

log = logging.getLogger("findesk.memory")


class MemoryClient:
    def __init__(self, base_url: str | None = None, *, timeout: float = 5.0) -> None:
        self._base_url = (base_url or get_settings().recall_base_url).rstrip("/")
        self._timeout = timeout

    async def remember(
        self,
        *,
        tenant_id: str,
        scope_key: str,
        run_id: str,
        content: str,
    ) -> bool:
        """Ingest one observation. Returns False (and logs) if memory is unavailable."""
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                resp = await client.post(
                    "/memory/ingest",
                    json={
                        "user_id": scope_key,
                        "session_id": run_id,
                        "content": content,
                        "tenant_id": tenant_id,
                    },
                )
                resp.raise_for_status()
                return True
        except (httpx.HTTPError, OSError) as exc:
            log.warning("memory ingest skipped (%s)", exc)
            return False

    async def recall(
        self,
        *,
        tenant_id: str,
        scope_key: str,
        query: str,
        token_budget: int = 800,
    ) -> list[dict[str, Any]]:
        """Budget-packed retrieval. Returns [] if memory is unavailable."""
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                resp = await client.post(
                    "/memory/retrieve",
                    json={
                        "user_id": scope_key,
                        "query": query,
                        "token_budget": token_budget,
                        "tenant_id": tenant_id,
                    },
                )
                resp.raise_for_status()
                return resp.json().get("memories", [])
        except (httpx.HTTPError, OSError) as exc:
            log.warning("memory recall skipped (%s)", exc)
            return []
