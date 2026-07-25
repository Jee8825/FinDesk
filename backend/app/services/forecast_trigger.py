"""Ledger-event → forecast recompute.

The forecast page promises "recomputed on every ledger event". This is the
deterministic trigger that keeps that promise: whenever a batch of ledger
commits lands (agent reconciliation or a human approval), enqueue one
``cash_forecast`` run for the tenant. Debounced — if a forecast run is already
queued or running for the tenant, the commit rides on that one instead of
piling up duplicates.

Call *after* the ledger transaction has committed: the run row must be visible
before the redis job is, or the worker drops the job on the floor.
"""

from __future__ import annotations

import logging

from findesk_shared import uuid7

from app.db import session_scope
from app.db.models import AgentRun
from app.db.repositories import RunRepo
from app.events.streams import enqueue_job

GRAPH = "cash_forecast"

log = logging.getLogger("findesk.forecast_trigger")


async def trigger_forecast_recompute(*, tenant_id: str, requested_by: str) -> str | None:
    """Enqueue a forecast recompute; returns the run id, or None if debounced."""
    run_id = uuid7()
    async with session_scope() as session:
        runs = RunRepo(session)
        if await runs.active_run(tenant_id, GRAPH) is not None:
            return None
        await runs.add(
            AgentRun(
                id=run_id,
                tenant_id=tenant_id,
                graph=GRAPH,
                params={"trigger": "ledger_commit"},
                requested_by=requested_by,
            )
        )
    await enqueue_job(f"job.{GRAPH}.requested@v1", tenant_id, run_id, {"params": {}})
    log.info("forecast recompute enqueued run=%s tenant=%s", run_id, tenant_id)
    return run_id
