"""Predictive memory pre-fetching.

Every other memory system is *reactive*: it fetches only when the agent asks,
paying retrieval latency on every turn. Recall borrows CPU/DB prefetching: a
light, low-latency LLM classifies the last few conversation turns into a likely
memory *cluster*, and Recall warms an in-memory (Redis) cache with that cluster's
units before the agent's formal query arrives. Hit-rate is tracked to tune the
predictor over time.

The cache is per-session with a TTL; unconsumed entries simply expire (no
persistent side effects).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from recall.config import Settings, get_settings
from recall.core import repository
from recall.db import get_redis, session_scope
from recall.db.models import PrefetchEvent
from recall.logging import get_logger
from recall.providers import EmbeddingProvider, LLMProvider

log = get_logger(__name__)

# Fallback clusters when the user has no labeled memories yet.
DEFAULT_CLUSTERS = [
    "coding-preferences",
    "cloud-deployment",
    "personal-info",
    "past-errors",
    "project-context",
]


def _key(session_id: str) -> str:
    return f"recall:prefetch:{session_id}"


@dataclass
class PrefetchOutcome:
    predicted_cluster: str
    staged: int


class PrefetchService:
    def __init__(
        self,
        llm: LLMProvider | None = None,
        embedder: EmbeddingProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        from recall.providers import get_embedder, get_llm

        self.llm = llm or get_llm()
        self.embedder = embedder or get_embedder()
        self.settings = settings or get_settings()

    async def candidate_clusters(self, user_id: str, tenant_id: str) -> list[str]:
        async with session_scope() as s:
            user_clusters = await repository.distinct_clusters(
                s, user_id=user_id, tenant_id=tenant_id
            )
        # Union of the user's own clusters and the defaults (dedup, stable order).
        seen: dict[str, None] = {}
        for c in [*user_clusters, *DEFAULT_CLUSTERS]:
            seen.setdefault(c, None)
        return list(seen)

    async def predict_cluster(self, recent_turns: list[str], clusters: list[str]) -> str:
        text = "\n".join(recent_turns[-self.settings.prefetch_window_turns :])
        prompt = f"Recent conversation turns:\n{text}\n\nWhich memory cluster is most relevant?"
        return await self.llm.classify(prompt, clusters, role="light")

    async def predict_and_warm(
        self, *, user_id: str, session_id: str, recent_turns: list[str], tenant_id: str = "default"
    ) -> PrefetchOutcome:
        clusters = await self.candidate_clusters(user_id, tenant_id)
        predicted = await self.predict_cluster(recent_turns, clusters)

        async with session_scope() as s:
            units = await repository.list_by_cluster(
                s, user_id=user_id, tenant_id=tenant_id, cluster=predicted
            )
            payload = [{"id": str(u.id), "content": u.content, "cluster": u.cluster} for u in units]
            s.add(
                PrefetchEvent(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session_id,
                    predicted_cluster=predicted,
                    num_staged=len(payload),
                    consumed=False,
                )
            )

        redis = get_redis()
        await redis.set(
            _key(session_id),
            json.dumps({"cluster": predicted, "ids": [p["id"] for p in payload]}),
            ex=self.settings.prefetch_cache_ttl_seconds,
        )
        log.info("prefetch.warmed", cluster=predicted, staged=len(payload))
        return PrefetchOutcome(predicted_cluster=predicted, staged=len(payload))

    async def staged_for_session(self, session_id: str) -> dict | None:
        raw = await get_redis().get(_key(session_id))
        return json.loads(raw) if raw else None

    async def mark_consumed(self, session_id: str, tenant_id: str = "default") -> None:
        """Record that a prefetch was used (drives hit-rate stats)."""
        from sqlalchemy import select, update

        async with session_scope() as s:
            latest = (
                await s.execute(
                    select(PrefetchEvent.id)
                    .where(
                        PrefetchEvent.session_id == session_id,
                        PrefetchEvent.tenant_id == tenant_id,
                        PrefetchEvent.consumed.is_(False),
                    )
                    .order_by(PrefetchEvent.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if latest is not None:
                await s.execute(
                    update(PrefetchEvent).where(PrefetchEvent.id == latest).values(consumed=True)
                )
