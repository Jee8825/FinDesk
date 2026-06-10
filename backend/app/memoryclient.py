"""Backend → Recall memory client (best-effort, per contracts/memory.md).

Used where learning happens on the backend side of the loop — e.g. a human
approval confirming a TDS pattern. Never blocks the caller: memory being down
costs us learning, not correctness.
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


async def remember(*, tenant_id: str, scope_key: str, session_id: str, content: str) -> bool:
    try:
        async with httpx.AsyncClient(
            base_url=get_settings().recall_base_url, timeout=5.0
        ) as client:
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
