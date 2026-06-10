"""Stream worker: consume job events, run graphs, emit run events.

Stateless and horizontally scalable — add replicas to scale throughput.
At-least-once delivery; graphs are idempotent per step_id.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import signal

import redis.asyncio as aioredis
from findesk_shared import uuid7

from findesk_agents.backend_client import BackendClient
from findesk_agents.config import get_settings
from findesk_agents.events import RedisEventEmitter
from findesk_agents.graphs.ping import graph as ping_graph
from findesk_agents.graphs.ping.state import PingState
from findesk_agents.graphs.reconciliation import graph as recon_graph
from findesk_agents.graphs.reconciliation.state import ReconState
from findesk_agents.memoryclient import MemoryClient

log = logging.getLogger("findesk.worker")


async def dispatch(redis: aioredis.Redis, msg: dict[str, str]) -> None:
    event = msg.get("event", "")
    run_id = msg.get("run_id", "")
    tenant_id = msg.get("tenant_id", "")
    payload = json.loads(msg.get("payload") or "{}")
    if not run_id or not tenant_id:
        log.warning("malformed job event dropped: %s", event)
        return

    emitter = RedisEventEmitter(redis, tenant_id=tenant_id, run_id=run_id)
    try:
        if event.startswith("job.ping."):
            state = PingState(
                tenant_id=tenant_id,
                run_id=run_id,
                params=payload.get("params", {}),
                emitter=emitter,
            )
            final = await ping_graph.run(state)
            await emitter.done("succeeded", summary=final.summary)
        elif event.startswith("job.reconciliation."):
            backend = BackendClient()
            try:
                recon_state = ReconState(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    document_id=payload.get("document_id") or "",  # empty = sweep run
                    emitter=emitter,
                    backend=backend,
                    memory=MemoryClient(),
                )
                recon_final = await recon_graph.run(recon_state)
                await emitter.done("succeeded", summary=recon_final.summary)
            finally:
                await backend.aclose()
        else:
            log.warning("no graph for event %s", event)
            await emitter.done("failed", summary=f"unknown job kind {event}")
    except Exception as exc:  # noqa: BLE001 — a run failure must not kill the worker
        log.exception("run %s failed", run_id)
        await emitter.done("failed", summary=str(exc))


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    redis = aioredis.from_url(settings.app_redis_url, decode_responses=True)
    with contextlib.suppress(aioredis.ResponseError):  # BUSYGROUP on restart
        await redis.xgroup_create(
            settings.jobs_stream_interactive, settings.jobs_consumer_group, mkstream=True
        )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    consumer = f"worker-{uuid7()[:8]}"
    log.info("worker %s consuming %s", consumer, settings.jobs_stream_interactive)
    while not stop.is_set():
        try:
            batches = await redis.xreadgroup(
                settings.jobs_consumer_group,
                consumer,
                {settings.jobs_stream_interactive: ">"},
                count=8,
                block=2000,
            )
            for _stream, entries in batches or []:
                for entry_id, msg in entries:
                    await dispatch(redis, msg)
                    await redis.xack(
                        settings.jobs_stream_interactive, settings.jobs_consumer_group, entry_id
                    )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — transient redis errors: back off, retry
            log.exception("worker loop error; retrying")
            await asyncio.sleep(1)

    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
