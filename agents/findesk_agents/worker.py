"""Stream worker: consume job events, run graphs, emit run events.

Stateless and horizontally scalable — add replicas to scale throughput.
At-least-once delivery; graphs are idempotent per step_id. One shared
BackendClient/MemoryClient per process (pooled connections, closed on
shutdown) — graphs receive them via state.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import signal
from typing import Any

import redis.asyncio as aioredis

from findesk_agents.backend_client import BackendClient
from findesk_agents.config import get_settings
from findesk_agents.events import RedisEventEmitter
from findesk_agents.graphs.anomaly_scan import graph as anomaly_graph
from findesk_agents.graphs.anomaly_scan.state import AnomalyState
from findesk_agents.graphs.cash_forecast import graph as forecast_graph
from findesk_agents.graphs.cash_forecast.state import ForecastState
from findesk_agents.graphs.collections import graph as collections_graph
from findesk_agents.graphs.collections.state import CollectionsState
from findesk_agents.graphs.enforcer import graph as enforcer_graph
from findesk_agents.graphs.enforcer.state import EnforcerState
from findesk_agents.graphs.ping import graph as ping_graph
from findesk_agents.graphs.ping.state import PingState
from findesk_agents.graphs.reconciliation import graph as recon_graph
from findesk_agents.graphs.reconciliation.state import ReconState
from findesk_agents.graphs.working_capital import graph as wc_graph
from findesk_agents.graphs.working_capital.state import WorkingCapitalState
from findesk_agents.memoryclient import MemoryClient

log = logging.getLogger("findesk.worker")

# job-event prefix → (graph module, state factory). ReconState additionally
# reads document_id ("" = sweep run); ping takes no clients.
GRAPHS = {
    "job.ping.": (
        ping_graph,
        lambda common, payload: PingState(**common, params=payload.get("params", {})),
    ),
    "job.reconciliation.": (
        recon_graph,
        lambda common, payload: ReconState(
            **common, document_id=payload.get("document_id") or ""
        ),
    ),
    "job.anomaly_scan.": (anomaly_graph, lambda common, payload: AnomalyState(**common)),
    "job.collections.": (collections_graph, lambda common, payload: CollectionsState(**common)),
    "job.forecast.": (forecast_graph, lambda common, payload: ForecastState(**common)),
    "job.cash_forecast.": (forecast_graph, lambda common, payload: ForecastState(**common)),
    "job.working_capital.": (wc_graph, lambda common, payload: WorkingCapitalState(**common)),
    "job.enforcer_tick.": (enforcer_graph, lambda common, payload: EnforcerState(**common)),
    "job.enforcer_45day.": (enforcer_graph, lambda common, payload: EnforcerState(**common)),
}


def _resolve(event: str):
    for prefix, entry in GRAPHS.items():
        if event.startswith(prefix):
            return entry
    return None


async def dispatch(
    redis: aioredis.Redis,
    msg: dict[str, str],
    backend: BackendClient,
    memory: MemoryClient,
) -> None:
    event = msg.get("event", "")
    run_id = msg.get("run_id", "")
    tenant_id = msg.get("tenant_id", "")
    try:
        payload: dict[str, Any] = json.loads(msg.get("payload") or "{}")
    except json.JSONDecodeError:
        payload = {}
    if not run_id or not tenant_id:
        log.warning("malformed job event dropped: %s", event)
        return

    emitter = RedisEventEmitter(redis, tenant_id=tenant_id, run_id=run_id)
    entry = _resolve(event)
    if entry is None:
        log.warning("no graph for event %s", event)
        await emitter.done("failed", summary=f"unknown job kind {event}")
        return

    graph, make_state = entry
    common: dict[str, Any] = {"tenant_id": tenant_id, "run_id": run_id, "emitter": emitter}
    if graph is not ping_graph:
        common |= {"backend": backend, "memory": memory}
    try:
        final = await graph.run(make_state(common, payload))
        await emitter.done("succeeded", summary=final.summary)
    except Exception as exc:  # noqa: BLE001 — a run failure must not kill the worker
        log.exception("run %s failed", run_id)
        # clean, bounded summary for the UI — full traceback stays in logs
        await emitter.done("failed", summary=f"{type(exc).__name__}: {str(exc)[:200]}")


async def reclaim_pending(
    redis: aioredis.Redis,
    settings: Any,
    backend: BackendClient,
    memory: MemoryClient,
    *,
    handler=dispatch,
) -> dict[str, int]:
    """Adopt stale pending entries; dead-letter poison ones.

    At-least-once needs an adoption path: an entry delivered to a worker that
    died before XACK sits in the group's PEL forever unless someone reclaims
    it. Entries idle past ``worker_reclaim_idle_ms`` are claimed here; anything
    already delivered ``worker_max_deliveries`` times is poison — it goes to
    the dead stream (operator visibility) and its run is marked failed, so the
    UI never shows an eternal spinner.
    """
    stream = settings.jobs_stream_interactive
    group = settings.jobs_consumer_group
    counts = {"retried": 0, "dead": 0}
    pending = await redis.xpending_range(
        stream, group, min="-", max="+", count=32, idle=settings.worker_reclaim_idle_ms
    )
    for p in pending:
        entry_id = p["message_id"]
        deliveries = int(p["times_delivered"])
        claimed = await redis.xclaim(
            stream,
            group,
            settings.worker_consumer_name,
            min_idle_time=settings.worker_reclaim_idle_ms,
            message_ids=[entry_id],
        )
        for cid, msg in claimed:
            if deliveries >= settings.worker_max_deliveries:
                await redis.xadd(
                    settings.jobs_dead_stream,
                    {**msg, "dead_reason": f"exceeded {deliveries} deliveries"},
                )
                run_id = msg.get("run_id", "")
                tenant_id = msg.get("tenant_id", "")
                if run_id and tenant_id:
                    emitter = RedisEventEmitter(redis, tenant_id=tenant_id, run_id=run_id)
                    await emitter.done(
                        "failed", summary=f"dead-lettered after {deliveries} deliveries"
                    )
                counts["dead"] += 1
            else:
                await handler(redis, msg, backend, memory)
                counts["retried"] += 1
            await redis.xack(stream, group, cid)
    if counts["retried"] or counts["dead"]:
        log.info("reclaimed pending: %s", counts)
    return counts


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

    backend = BackendClient()
    memory = MemoryClient()
    consumer = settings.worker_consumer_name
    log.info("worker %s consuming %s", consumer, settings.jobs_stream_interactive)
    last_reclaim = 0.0
    while not stop.is_set():
        try:
            now = loop.time()
            if now - last_reclaim >= settings.worker_reclaim_every_s:
                last_reclaim = now
                await reclaim_pending(redis, settings, backend, memory)
            batches = await redis.xreadgroup(
                settings.jobs_consumer_group,
                consumer,
                {settings.jobs_stream_interactive: ">"},
                count=8,
                block=2000,
            )
            for _stream, entries in batches or []:
                for entry_id, msg in entries:
                    await dispatch(redis, msg, backend, memory)
                    await redis.xack(
                        settings.jobs_stream_interactive, settings.jobs_consumer_group, entry_id
                    )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — transient redis errors: back off, retry
            log.exception("worker loop error; retrying")
            await asyncio.sleep(1)

    await backend.aclose()
    await memory.aclose()
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
