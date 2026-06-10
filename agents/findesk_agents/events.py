"""Run-event emitter — shapes from contracts/events.md, transport Redis stream.

The worker never touches the app DB (agents/CLAUDE.md rule 2): it emits
run.step / run.done events to ``agents:events``; the backend consumer persists
them and relays to SSE.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

import redis.asyncio as aioredis
from findesk_shared import uuid7

from findesk_agents.config import get_settings


@runtime_checkable
class EventEmitter(Protocol):
    """Graphs depend on this protocol so unit tests can use a fake."""

    async def step(self, name: str, status: str, step_id: str, **detail: Any) -> None: ...
    async def done(self, status: str, summary: str = "") -> None: ...


class RedisEventEmitter:
    def __init__(self, redis: aioredis.Redis, *, tenant_id: str, run_id: str) -> None:
        self._redis = redis
        self._tenant_id = tenant_id
        self._run_id = run_id

    async def _emit(self, event: str, payload: dict[str, Any]) -> None:
        await self._redis.xadd(
            get_settings().events_stream,
            {
                "event": event,
                "id": uuid7(),
                "tenant_id": self._tenant_id,
                "occurred_at": datetime.now(UTC).isoformat(),
                "run_id": self._run_id,
                "payload": json.dumps(payload),
            },
        )

    async def step(self, name: str, status: str, step_id: str, **detail: Any) -> None:
        await self._emit(
            "run.step@v1", {"step_id": step_id, "name": name, "status": status, **detail}
        )

    async def done(self, status: str, summary: str = "") -> None:
        await self._emit("run.done@v1", {"status": status, "summary": summary})
