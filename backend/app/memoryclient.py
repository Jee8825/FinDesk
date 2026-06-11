"""Backend → Recall memory client (best-effort, per contracts/memory.md).

Used where learning or belief management happens on the backend side of the
loop — approvals confirming patterns, conflict cards reading/resolving the
engine's conflict log. Read paths return empty on failure; write paths return
False: memory being down costs us learning, never correctness.

One shared AsyncClient per process (connection pooling); closed via
:func:`close_memory_client` from the app's lifespan hook.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

_client_instance: httpx.AsyncClient | None = None
# bound concurrent fan-outs (radar/conflicts batching) so a big tenant can't
# stampede the memory service
MEMORY_CONCURRENCY = asyncio.Semaphore(8)


def _client() -> httpx.AsyncClient:
    global _client_instance
    if _client_instance is None or _client_instance.is_closed:
        _client_instance = httpx.AsyncClient(
            base_url=get_settings().recall_base_url, timeout=5.0
        )
    return _client_instance


async def close_memory_client() -> None:
    global _client_instance
    if _client_instance is not None and not _client_instance.is_closed:
        await _client_instance.aclose()
    _client_instance = None


async def remember(*, tenant_id: str, scope_key: str, session_id: str, content: str) -> bool:
    try:
        async with MEMORY_CONCURRENCY:
            resp = await _client().post(
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
        async with MEMORY_CONCURRENCY:
            resp = await _client().get(
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
    """Map memory_id → {content, confidence} via budget-packed retrieval."""
    try:
        async with MEMORY_CONCURRENCY:
            resp = await _client().post(
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
        async with MEMORY_CONCURRENCY:
            resp = await _client().delete(f"/memory/{memory_id}")
        resp.raise_for_status()
        return True
    except (httpx.HTTPError, OSError) as exc:
        log.warning("memory delete failed (%s)", exc)
        return False
