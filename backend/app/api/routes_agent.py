"""Agent control plane: start runs, inspect, live SSE stream."""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import memoryclient
from app.auth.deps import Auth
from app.config import get_settings
from app.db import session_scope
from app.db.models import AgentRun
from app.db.repositories import RunRepo
from app.events.streams import enqueue_job, get_redis, subscribe_run

router = APIRouter(tags=["agent"])

# a healthy worker re-polls the stream every 2s (xreadgroup block=2000);
# 30s of consumer idle means it is gone or wedged
WORKER_IDLE_THRESHOLD_MS = 30_000

# grows as graphs land (docs/architecture/01 §2)
KNOWN_GRAPHS = {
    "ping",
    "reconciliation",
    "anomaly_scan",
    "collections",
    "cash_forecast",
    "working_capital",
    "enforcer_45day",
}


class RunCreate(BaseModel):
    graph: str
    params: dict[str, Any] = Field(default_factory=dict)


class StepOut(BaseModel):
    step_id: str
    name: str
    status: str
    detail: dict[str, Any]
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None


class RunOut(BaseModel):
    run_id: str
    graph: str
    status: str
    params: dict[str, Any]
    created_at: str | None = None
    steps: list[StepOut] = []


def _step_out(s: Any) -> StepOut:
    """Timing from the row lifecycle: created at 'started', updated on finish."""
    done = s.status in {"finished", "failed"}
    duration_ms = (
        int((s.updated_at - s.created_at).total_seconds() * 1000) if done else None
    )
    return StepOut(
        step_id=s.step_id,
        name=s.name,
        status=s.status,
        detail=s.detail,
        started_at=s.created_at.isoformat(),
        finished_at=s.updated_at.isoformat() if done else None,
        duration_ms=duration_ms,
    )


@router.get("/agent/health")
async def agent_health(auth: Auth) -> dict[str, bool]:
    """Real liveness for the sidebar badge — never guesses, never raises."""
    settings = get_settings()
    worker = False
    try:
        consumers = await get_redis().xinfo_consumers(
            settings.jobs_stream_interactive, settings.jobs_consumer_group
        )
        worker = any(int(c.get("idle", 1 << 62)) < WORKER_IDLE_THRESHOLD_MS for c in consumers)
    except Exception:  # noqa: BLE001 — stream/group missing or redis down = not live
        worker = False
    return {"worker": worker, "memory": await memoryclient.ping()}


@router.post("/agent/runs", status_code=status.HTTP_202_ACCEPTED, response_model=RunOut)
async def create_run(body: RunCreate, auth: Auth) -> RunOut:
    if body.graph not in KNOWN_GRAPHS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown graph {body.graph!r}")
    run = AgentRun(
        tenant_id=auth.tenant_id,
        graph=body.graph,
        params=body.params,
        requested_by=auth.user_id,
    )
    async with session_scope() as session:
        await RunRepo(session).add(run)
    await enqueue_job(
        f"job.{body.graph}.requested@v1", auth.tenant_id, run.id, {"params": body.params}
    )
    return RunOut(run_id=run.id, graph=run.graph, status="queued", params=run.params)


@router.get("/agent/runs", response_model=list[RunOut])
async def list_runs(auth: Auth) -> list[RunOut]:
    async with session_scope() as session:
        runs = await RunRepo(session).list_for_tenant(auth.tenant_id)
        return [
            RunOut(
                run_id=r.id,
                graph=r.graph,
                status=r.status,
                params=r.params,
                created_at=r.created_at.isoformat(),
            )
            for r in runs
        ]


@router.get("/agent/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: str, auth: Auth) -> RunOut:
    async with session_scope() as session:
        repo = RunRepo(session)
        run = await repo.by_id(run_id, auth.tenant_id)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
        steps = await repo.steps(run_id)
        return RunOut(
            run_id=run.id,
            graph=run.graph,
            status=run.status,
            params=run.params,
            created_at=run.created_at.isoformat(),
            steps=[_step_out(s) for s in steps],
        )


@router.get("/agent/runs/{run_id}/stream")
async def stream_run(run_id: str, auth: Auth) -> StreamingResponse:
    # tenancy check before anything is streamed
    async with session_scope() as session:
        run = await RunRepo(session).by_id(run_id, auth.tenant_id)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")

    async def gen():
        # Order matters: a relay task subscribes to the live channel FIRST,
        # then we read the persisted replay — any event landing in between is
        # buffered in the queue and deduped below, so nothing is lost (the old
        # replay-then-subscribe order dropped events emitted in the gap, and
        # wait_for(anext()) could cancel the generator mid-step).
        queue: asyncio.Queue[str] = asyncio.Queue()

        async def relay() -> None:
            async for data in subscribe_run(run_id):
                await queue.put(data)

        relay_task = asyncio.create_task(relay())
        seen: set[tuple[str, str]] = set()

        def key(item: dict) -> tuple[str, str]:
            return (item.get("step_id", item.get("event", "")), item.get("status", ""))

        try:
            async with session_scope() as session:
                repo = RunRepo(session)
                run_row = await repo.by_id(run_id, auth.tenant_id)
                steps = await repo.steps(run_id)
            terminal = run_row.status in {"succeeded", "failed", "cancelled"}
            for s in steps:
                item = {
                    "event": "run.step@v1",
                    "step_id": s.step_id,
                    "name": s.name,
                    "status": s.status,
                }
                seen.add(key(item))
                yield f"data: {json.dumps(item)}\n\n"
            if terminal:
                yield f"data: {json.dumps({'event': 'run.done@v1', 'status': run_row.status})}\n\n"
                return

            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                item = json.loads(data)
                if item.get("event", "").startswith("run.step@") and key(item) in seen:
                    continue  # already sent during replay
                seen.add(key(item))
                yield f"data: {data}\n\n"
                if item.get("event", "").startswith("run.done@"):
                    return
        finally:
            relay_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await relay_task

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
