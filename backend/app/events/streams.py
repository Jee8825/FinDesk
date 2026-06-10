"""Redis plumbing: job producer, run-events consumer, SSE pub/sub bridge.

Flow (contracts/events.md):
  backend XADD job.*           -> agents:interactive   (worker consumes)
  worker  XADD run.step/done   -> agents:events        (we consume below)
  consumer persists steps/status, then PUBLISH run:<id> for live SSE.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from findesk_shared import uuid7

from app.config import get_settings
from app.db import session_scope
from app.db.repositories import RunRepo

log = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().app_redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def envelope(
    event: str, tenant_id: str, payload: dict[str, Any], run_id: str | None = None
) -> dict[str, str]:
    return {
        "event": event,
        "id": uuid7(),
        "tenant_id": tenant_id,
        "occurred_at": datetime.now(UTC).isoformat(),
        "run_id": run_id or "",
        "payload": json.dumps(payload),
    }


async def enqueue_job(event: str, tenant_id: str, run_id: str, payload: dict[str, Any]) -> None:
    settings = get_settings()
    await get_redis().xadd(
        settings.jobs_stream_interactive, envelope(event, tenant_id, payload, run_id)
    )


# ---------------------------------------------------------------- consumer

async def _handle_event(msg: dict[str, str]) -> None:
    event = msg.get("event", "")
    run_id = msg.get("run_id") or None
    if not run_id:
        return
    payload = json.loads(msg.get("payload") or "{}")
    now = datetime.now(UTC)

    async with session_scope() as session:
        runs = RunRepo(session)
        run = await runs.by_id_any_tenant(run_id)
        if run is None:
            log.warning("event for unknown run %s", run_id)
            return
        if event.startswith("run.step@"):
            if run.status == "queued":
                await runs.set_status(run_id, "running", started_at=now)
            await runs.upsert_step(
                run_id=run_id,
                tenant_id=run.tenant_id,
                step_id=payload.get("step_id", uuid7()),
                name=payload.get("name", "step"),
                status=payload.get("status", "started"),
                detail={k: v for k, v in payload.items() if k not in {"step_id", "name", "status"}},
            )
        elif event.startswith("run.done@"):
            status = payload.get("status", "succeeded")
            await runs.set_status(run_id, status, finished_at=now)

    # relay for live SSE subscribers (after persistence, so replay+live is gapless)
    channel = get_settings().run_channel_prefix + run_id
    await get_redis().publish(channel, json.dumps({"event": event, **payload}))


async def consume_run_events(stop: asyncio.Event) -> None:
    """Background task: persist worker events from agents:events (at-least-once)."""
    settings = get_settings()
    r = get_redis()
    with contextlib.suppress(aioredis.ResponseError):  # BUSYGROUP on restart
        await r.xgroup_create(settings.events_stream, settings.events_consumer_group, mkstream=True)

    consumer = f"backend-{uuid7()[:8]}"
    while not stop.is_set():
        try:
            batches = await r.xreadgroup(
                settings.events_consumer_group,
                consumer,
                {settings.events_stream: ">"},
                count=32,
                block=2000,
            )
            for _stream, entries in batches or []:
                for entry_id, msg in entries:
                    try:
                        await _handle_event(msg)
                        await r.xack(
                            settings.events_stream, settings.events_consumer_group, entry_id
                        )
                    except Exception:  # noqa: BLE001 — keep the consumer alive
                        log.exception("failed handling event %s", entry_id)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — redis hiccup: back off and retry
            log.exception("event consumer error; retrying")
            await asyncio.sleep(1)


async def subscribe_run(run_id: str):
    """Async iterator of live event JSON strings for one run (SSE source)."""
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(get_settings().run_channel_prefix + run_id)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield message["data"]
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()
