"""Memory operations: ingest, retrieve, why, promote, delete, conflicts, GDPR."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from recall.api.deps import engine_dep
from recall.core.engine import RecallEngine
from recall.core.scoping import ScopeError
from recall.core.types import (
    ConflictDTO,
    ConsolidateRequest,
    IngestRequest,
    IngestResult,
    MemoryUnitDTO,
    PrefetchRequest,
    PrefetchResult,
    PromoteRequest,
    RetrieveRequest,
    RetrieveResult,
    WhyResult,
)

router = APIRouter(tags=["memory"])


@router.post("/memory/ingest", response_model=IngestResult)
async def ingest(req: IngestRequest, engine: RecallEngine = Depends(engine_dep)) -> IngestResult:
    return await engine.ingest(req)


@router.post("/memory/retrieve", response_model=RetrieveResult)
async def retrieve(
    req: RetrieveRequest, engine: RecallEngine = Depends(engine_dep)
) -> RetrieveResult:
    return await engine.retrieve(req)


@router.get("/memory/user-owned", response_model=list[MemoryUnitDTO])
async def user_owned(
    user_id: str,
    tenant_id: str = "default",
    engine: RecallEngine = Depends(engine_dep),
) -> list[MemoryUnitDTO]:
    """GDPR transparency: every memory the user is entitled to inspect/delete."""
    return await engine.list_user_owned(user_id, tenant_id)


@router.get("/memory/{memory_id}/why", response_model=WhyResult)
async def why(memory_id: uuid.UUID, engine: RecallEngine = Depends(engine_dep)) -> WhyResult:
    return await engine.why(memory_id)


@router.delete("/memory/{memory_id}")
async def delete(
    memory_id: uuid.UUID,
    cascade: bool = Query(default=True),
    engine: RecallEngine = Depends(engine_dep),
) -> dict:
    deleted = await engine.delete(memory_id, cascade=cascade)
    return {"deleted": True, "provenance_nodes_removed": deleted}


@router.post("/memory/promote")
async def promote(req: PromoteRequest, engine: RecallEngine = Depends(engine_dep)) -> dict:
    try:
        await engine.promote(req.memory_id, req.scope, req.team_id, req.is_orchestrator)
    except ScopeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"promoted": True}


@router.post("/memory/prefetch", response_model=PrefetchResult)
async def prefetch(
    req: PrefetchRequest, engine: RecallEngine = Depends(engine_dep)
) -> PrefetchResult:
    """Warm the cache with the memory cluster most relevant to recent turns."""
    outcome = await engine.prefetch(
        user_id=req.user_id,
        session_id=req.session_id,
        recent_turns=req.recent_turns,
        tenant_id=req.tenant_id,
    )
    return PrefetchResult(predicted_cluster=outcome.predicted_cluster, staged=outcome.staged)


@router.post("/admin/consolidate")
async def consolidate(
    req: ConsolidateRequest, engine: RecallEngine = Depends(engine_dep)
) -> dict:
    """Run the consolidation pass for a user (tier promotion, crystallization,
    procedural extraction, tombstone sweep, compaction)."""
    return await engine.consolidate(req.user_id, req.tenant_id)


@router.get("/conflicts", response_model=list[ConflictDTO])
async def conflicts(
    user_id: str,
    tenant_id: str = "default",
    limit: int = 100,
    engine: RecallEngine = Depends(engine_dep),
) -> list[ConflictDTO]:
    return await engine.list_conflicts(user_id, tenant_id, limit)
