"""RecallEngine — the public façade over the memory engine.

Wires together ingestion, conflict detection/resolution, provenance, decay-based
retrieval, confidence accumulation, and scoping into the operations the API and
SDK expose. Construct one per process via :func:`get_engine`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from recall.config import Settings, get_settings
from recall.core import (
    confidence,
    conflict,
    consolidation,
    ingestion,
    repository,
    retrieval,
    scoping,
)
from recall.core.prefetch import PrefetchOutcome, PrefetchService
from recall.core.provenance import ProvenanceService
from recall.core.types import (
    ConflictDTO,
    IngestRequest,
    IngestResult,
    MemoryUnitDTO,
    RetrievedMemory,
    RetrieveRequest,
    RetrieveResult,
    WhyResult,
)
from recall.db import session_scope
from recall.db.models import ConflictLog, MemoryUnit
from recall.logging import get_logger
from recall.providers import EmbeddingProvider, LLMProvider, get_embedder, get_llm

log = get_logger(__name__)


def _to_dto(unit: MemoryUnit, now: datetime | None = None) -> MemoryUnitDTO:
    from recall.core import decay

    now = now or datetime.now(UTC)
    return MemoryUnitDTO(
        id=unit.id,
        user_id=unit.user_id,
        tier=unit.tier,
        content=unit.content,
        strength=decay.current_strength(
            unit.strength, unit.decay_lambda, unit.strength_updated_at, now
        ),
        confidence=unit.confidence,
        status=unit.status,
        scope=unit.scope,
        team_id=unit.team_id,
        cluster=unit.cluster,
        retrieval_count=unit.retrieval_count,
        created_at=unit.created_at,
        last_retrieved_at=unit.last_retrieved_at,
    )


class RecallEngine:
    def __init__(
        self,
        llm: LLMProvider | None = None,
        embedder: EmbeddingProvider | None = None,
        provenance: ProvenanceService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.llm = llm or get_llm()
        self.embedder = embedder or get_embedder()
        self.provenance = provenance or ProvenanceService()
        self.settings = settings or get_settings()
        self.prefetch_service = PrefetchService(self.llm, self.embedder, self.settings)

    # ----------------------------- ingest -----------------------------
    async def ingest(self, req: IngestRequest) -> IngestResult:
        facts = await ingestion.extract_facts(self.llm, req.content)
        embeddings = await ingestion.embed_facts(self.embedder, facts)

        units: list[MemoryUnitDTO] = []
        conflicts_detected = 0

        async with session_scope() as s:
            existing_semantic = await repository.list_semantic_for_user(
                s, user_id=req.user_id, tenant_id=req.tenant_id
            )
            for fact, emb in zip(facts, embeddings, strict=True):
                if fact.tier == "semantic":
                    nearest = conflict.find_nearest(
                        emb, existing_semantic, self.settings.conflict_distance_threshold
                    )
                    if nearest is not None:
                        conflicts_detected += 1
                        unit = await self._ingest_with_conflict(
                            s, req, fact, emb, existing=nearest[0], distance=nearest[1]
                        )
                        existing_semantic.append(unit)
                        units.append(_to_dto(unit))
                        continue

                unit = await ingestion.persist_fact(
                    s,
                    fact=fact,
                    embedding=emb,
                    user_id=req.user_id,
                    tenant_id=req.tenant_id,
                    scope=req.scope,
                    team_id=req.team_id,
                    session_id=req.session_id,
                    settings=self.settings,
                )
                if fact.tier == "semantic":
                    existing_semantic.append(unit)
                await self.provenance.record_direct(
                    unit.id,
                    session_id=req.session_id,
                    confidence=unit.confidence,
                    note=fact.content,
                )
                units.append(_to_dto(unit))

        return IngestResult(units=units, conflicts_detected=conflicts_detected)

    async def _ingest_with_conflict(
        self,
        s: AsyncSession,
        req: IngestRequest,
        fact,
        emb: list[float],
        *,
        existing: MemoryUnit,
        distance: float,
    ) -> MemoryUnit:
        """Resolve a detected conflict, persist the surviving belief, log it."""
        decision = await conflict.resolve(
            self.llm, existing=existing, new_content=fact.content, new_confidence=fact.confidence
        )

        # The surviving belief's text depends on the resolution type.
        surviving_text = decision.resolved_belief or fact.content
        if surviving_text == fact.content:
            surviving_emb = emb
        else:
            surviving_emb = (await self.embedder.embed([surviving_text]))[0]

        new_conf = {
            "auto_resolved": confidence.corroborate(
                max(existing.confidence, fact.confidence), existing.corroboration_count
            ),
            "merged": confidence.corroborate(
                max(existing.confidence, fact.confidence), existing.corroboration_count
            ),
            "flagged": confidence.contradict(fact.confidence, existing.confidence),
        }.get(decision.resolution, fact.confidence)

        unit = await repository.insert_memory(
            s,
            user_id=req.user_id,
            tenant_id=req.tenant_id,
            tier="semantic",
            content=surviving_text,
            embedding=surviving_emb,
            decay_lambda=self.settings.decay_lambda("semantic"),
            confidence=new_conf,
            scope=req.scope,
            team_id=req.team_id,
            cluster=fact.cluster or existing.cluster,
            source_session_id=req.session_id,
        )

        # For decisive resolutions, retire the superseded belief.
        if decision.resolution in ("auto_resolved", "merged"):
            await repository.set_status(s, existing.id, "tombstoned")

        await conflict.log_conflict(
            s,
            user_id=req.user_id,
            tenant_id=req.tenant_id,
            memory_a=existing.id,
            memory_b=unit.id,
            distance=distance,
            resolution=decision.resolution,
            resolved_belief=surviving_text,
            resolved_memory_id=unit.id,
            rationale=decision.rationale,
        )

        # Provenance: new belief is supported directly, contradicts the old, and
        # is resolved from it.
        await self.provenance.record_direct(
            unit.id, session_id=req.session_id, confidence=new_conf, note=fact.content
        )
        await self.provenance.record_contradiction(
            existing.id, session_id=req.session_id, weight=0.12, note=fact.content
        )
        await self.provenance.link_resolution(unit.id, [existing.id])

        log.info(
            "conflict.resolved",
            resolution=decision.resolution,
            distance=round(distance, 3),
            existing=str(existing.id),
            new=str(unit.id),
        )
        return unit

    # ----------------------------- retrieve -----------------------------
    async def retrieve(self, req: RetrieveRequest) -> RetrieveResult:
        query_emb = (await self.embedder.embed([req.query]))[0]
        fetch_limit = max(30, req.token_budget // 50)
        async with session_scope() as s:
            candidates = await repository.search_similar(
                s,
                embedding=query_emb,
                user_id=req.user_id,
                tenant_id=req.tenant_id,
                limit=fetch_limit,
                scope=req.scope,
                team_id=req.team_id,
            )
            scored = retrieval.score_candidates(candidates)
            packed, used = await retrieval.pack_to_budget(scored, req.token_budget, self.llm)

            now = datetime.now(UTC)
            from recall.core import decay

            results: list[RetrievedMemory] = []
            for item in packed:
                u = item.unit
                new_strength = decay.reinforce(
                    u.strength,
                    u.decay_lambda,
                    u.strength_updated_at,
                    self.settings.reinforcement_factor,
                    now,
                )
                await repository.apply_reinforcement(s, u.id, new_strength)
                results.append(
                    RetrievedMemory(
                        id=u.id,
                        content=item.text,
                        tier=u.tier,
                        score=item.score,
                        strength=new_strength,
                        confidence=u.confidence,
                        summarized=item.summarized,
                    )
                )

        cache_hit = await self._consume_prefetch(req, results)
        return RetrieveResult(
            memories=results,
            tokens_used=used,
            token_budget=req.token_budget,
            cache_hit=cache_hit,
        )

    async def _consume_prefetch(
        self, req: RetrieveRequest, results: list[RetrievedMemory]
    ) -> bool:
        """If this session had warmed memories and any were served, count a hit."""
        if not req.session_id:
            return False
        staged = await self.prefetch_service.staged_for_session(req.session_id)
        if not staged:
            return False
        staged_ids = set(staged.get("ids", []))
        if any(str(m.id) in staged_ids for m in results):
            await self.prefetch_service.mark_consumed(req.session_id, req.tenant_id)
            return True
        return False

    # ----------------------------- why / manage -----------------------------
    async def why(self, memory_id: uuid.UUID) -> WhyResult:
        chain = await self.provenance.explain(memory_id)
        return WhyResult(
            memory_id=memory_id,
            confidence=chain.get("confidence"),
            status=chain.get("status"),
            explanation=chain.get("explanation", ""),
            evidence=chain.get("evidence", []),
            resolved_from=chain.get("resolved_from", []),
        )

    async def promote(
        self,
        memory_id: uuid.UUID,
        scope,
        team_id: str | None,
        is_orchestrator: bool = False,
    ) -> None:
        scoping.validate_promotion(
            target_scope=scope, is_orchestrator=is_orchestrator, team_id=team_id
        )
        async with session_scope() as s:
            await repository.update_scope(s, memory_id, scope, team_id)

    # ------------------------- consolidation / prefetch -------------------------
    async def consolidate(self, user_id: str, tenant_id: str = "default") -> dict:
        async with session_scope() as s:
            report = await consolidation.consolidate_user(
                s, self.embedder, tenant_id=tenant_id, user_id=user_id, settings=self.settings
            )
        return report.__dict__

    async def prefetch(
        self,
        *,
        user_id: str,
        session_id: str,
        recent_turns: list[str],
        tenant_id: str = "default",
    ) -> PrefetchOutcome:
        return await self.prefetch_service.predict_and_warm(
            user_id=user_id,
            session_id=session_id,
            recent_turns=recent_turns,
            tenant_id=tenant_id,
        )

    async def delete(self, memory_id: uuid.UUID, cascade: bool = True) -> int:
        deleted_nodes = 0
        if cascade:
            deleted_nodes = await self.provenance.cascade_delete(memory_id)
        async with session_scope() as s:
            await repository.delete_memory(s, memory_id)
        return deleted_nodes

    async def list_user_owned(
        self, user_id: str, tenant_id: str = "default"
    ) -> list[MemoryUnitDTO]:
        async with session_scope() as s:
            units = await repository.list_user_owned(s, user_id=user_id, tenant_id=tenant_id)
            return [_to_dto(u) for u in units]

    async def list_conflicts(
        self, user_id: str, tenant_id: str = "default", limit: int = 100
    ) -> list[ConflictDTO]:
        async with session_scope() as s:
            rows = (
                await s.execute(
                    select(ConflictLog)
                    .where(ConflictLog.tenant_id == tenant_id, ConflictLog.user_id == user_id)
                    .order_by(ConflictLog.created_at.desc())
                    .limit(limit)
                )
            ).scalars().all()
            return [
                ConflictDTO(
                    id=r.id,
                    user_id=r.user_id,
                    semantic_distance=r.semantic_distance,
                    resolution=r.resolution,
                    resolved_belief=r.resolved_belief,
                    rationale=r.rationale,
                    created_at=r.created_at,
                )
                for r in rows
            ]


_engine: RecallEngine | None = None


def get_engine() -> RecallEngine:
    global _engine
    if _engine is None:
        _engine = RecallEngine()
    return _engine
