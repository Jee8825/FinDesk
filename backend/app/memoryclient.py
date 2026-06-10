"""Backend → Recall memory client (best-effort, per contracts/memory.md).

Used where learning or belief management happens on the backend side of the
loop — approvals confirming patterns, conflict cards reading/resolving the
engine's conflict log. Read paths return empty on failure; write paths return
False: memory being down costs us learning, never correctness.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=get_settings().recall_base_url, timeout=5.0)


async def remember(*, tenant_id: str, scope_key: str, session_id: str, content: str) -> bool:
    try:
        async with _client() as client:
            resp = await client.post(
                "/memory/ingest",
                json={
                    "user_id": scope_key,
                    "session_id": session_id,
                    "content": content,
                    "tenant_id": tenant_id,
                },
            )
            resp.raise_for_status()
            return True
    except (httpx.HTTPError, OSError) as exc:
        log.warning("memory ingest skipped (%s)", exc)
        return False


async def list_conflicts(*, tenant_id: str, scope_key: str) -> list[dict[str, Any]]:
    try:
        async with _client() as client:
            resp = await client.get(
                "/conflicts", params={"user_id": scope_key, "tenant_id": tenant_id}
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, OSError) as exc:
        log.warning("memory conflicts unavailable (%s)", exc)
        return []


async def retrieve_units(
    *, tenant_id: str, scope_key: str, query: str, token_budget: int = 800
) -> dict[str, dict[str, Any]]:
    """Map memory_id → {content, confidence} via budget-packed retrieval.

    Used by conflict sync to join both sides of an engine conflict to their
    contents — near-identical beliefs both rank at the top for the resolved
    belief as query.
    """
    try:
        async with _client() as client:
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
            return {str(m["id"]): m for m in resp.json().get("memories", [])}
    except (httpx.HTTPError, OSError) as exc:
        log.warning("memory retrieve unavailable (%s)", exc)
        return {}


async def delete_memory(memory_id: str) -> bool:
    try:
        async with _client() as client:
            resp = await client.delete(f"/memory/{memory_id}")
            resp.raise_for_status()
            return True
    except (httpx.HTTPError, OSError) as exc:
        log.warning("memory delete failed (%s)", exc)
        return False
