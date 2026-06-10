"""Agent control plane: start runs, inspect, live SSE stream."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth.deps import Auth
from app.db import session_scope
from app.db.models import AgentRun
from app.db.repositories import RunRepo
from app.events.streams import enqueue_job, subscribe_run

router = APIRouter(tags=["agent"])

KNOWN_GRAPHS = {"ping"}  # grows as graphs land (docs/architecture/01 §2)


class RunCreate(BaseModel):
    graph: str
    params: dict[str, Any] = Field(default_factory=dict)


class StepOut(BaseModel):
    step_id: str
    name: str
    status: str
    detail: dict[str, Any]


class RunOut(BaseModel):
    run_id: str
    graph: str
    status: str
    params: dict[str, Any]
    steps: list[StepOut] = []


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
            RunOut(run_id=r.id, graph=r.graph, status=r.status, params=r.params) for r in runs
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
            steps=[
                StepOut(step_id=s.step_id, name=s.name, status=s.status, detail=s.detail)
                for s in steps
            ],
        )


@router.get("/agent/runs/{run_id}/stream")
async def stream_run(run_id: str, auth: Auth) -> StreamingResponse:
    async with session_scope() as session:
        repo = RunRepo(session)
        run = await repo.by_id(run_id, auth.tenant_id)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
        steps = await repo.steps(run_id)
        terminal = run.status in {"succeeded", "failed", "cancelled"}
        replay = [
            {"event": "run.step@v1", "step_id": s.step_id, "name": s.name, "status": s.status}
            for s in steps
        ]
        if terminal:
            replay.append({"event": "run.done@v1", "status": run.status})

    async def gen():
        for item in replay:
            yield f"data: {json.dumps(item)}\n\n"
        if terminal:
            return
        live = subscribe_run(run_id)
        try:
            while True:
                try:
                    data = await asyncio.wait_for(anext(live), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {data}\n\n"
                if json.loads(data).get("event", "").startswith("run.done@"):
                    return
        finally:
            await live.aclose()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
