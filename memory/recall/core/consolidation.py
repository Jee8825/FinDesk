"""Consolidation — the scheduled self-organization pass.

Run periodically (e.g. via a cron / Function Compute trigger). It performs the
"living system" maintenance that distinguishes Recall from additive stores:

* **tombstone sweep** — soft-delete memories whose decayed strength fell below τ.
* **compaction** — hard-delete tombstones older than a retention window so they
  don't grow unboundedly (audit trail preserved until then).
* **dormancy + crystallization** — drift confidence down for long-unreferenced
  beliefs; freeze (crystallize) beliefs whose confidence is high.
* **procedural extraction** — detect repeated multi-step workflows in the agent's
  tool-call history and crystallize them into Tier-3 procedural memories, with no
  agent code changes required.

The pure detection logic (``find_repeated_workflows``) is unit-tested without a
database.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from recall.config import Settings, get_settings
from recall.core import confidence, decay, repository
from recall.db.models import AgentRun, MemoryUnit, ToolCall
from recall.logging import get_logger
from recall.providers import EmbeddingProvider

log = get_logger(__name__)


@dataclass
class ConsolidationReport:
    tombstoned: int = 0
    compacted: int = 0
    crystallized_beliefs: int = 0
    procedural_created: int = 0
    dormant_drifted: int = 0


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------- procedural extraction ---------------------------

def find_repeated_workflows(
    run_sequences: list[list[str]],
    *,
    min_len: int = 2,
    min_repeats: int = 3,
    max_len: int = 6,
) -> list[tuple[tuple[str, ...], int]]:
    """Find contiguous tool-call subsequences repeated across runs.

    ``run_sequences`` is a list of per-run tool-name sequences. Returns
    ``(workflow, count)`` pairs where ``workflow`` (length in [min_len, max_len])
    appears in at least ``min_repeats`` distinct runs, longest/most-frequent
    first. Shorter subsumed patterns of a returned longer one are dropped.
    """
    counts: Counter[tuple[str, ...]] = Counter()
    for seq in run_sequences:
        seen_in_run: set[tuple[str, ...]] = set()
        for n in range(min_len, min(max_len, len(seq)) + 1):
            for i in range(len(seq) - n + 1):
                gram = tuple(seq[i : i + n])
                if gram not in seen_in_run:
                    seen_in_run.add(gram)
                    counts[gram] += 1

    qualifying = {g: c for g, c in counts.items() if c >= min_repeats}
    # Drop a pattern if a strictly longer qualifying pattern contains it with the
    # same count (it is subsumed).
    result = []
    for gram, count in sorted(qualifying.items(), key=lambda kv: (-len(kv[0]), -kv[1])):
        if any(
            len(other) > len(gram) and count <= ocount and _contains(other, gram)
            for other, ocount in qualifying.items()
        ):
            continue
        result.append((gram, count))
    return result


def _contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    n = len(needle)
    return any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


# ------------------------------- DB operations -------------------------------

async def sweep_tombstones(session: AsyncSession, *, tenant_id: str, settings: Settings) -> int:
    """Tombstone active units whose current strength is below τ."""
    now = _now()
    rows = (
        await session.execute(
            select(MemoryUnit).where(
                MemoryUnit.tenant_id == tenant_id,
                MemoryUnit.status == "active",
            )
        )
    ).scalars().all()
    # The query already excludes crystallized units (status != "active"), so
    # high-confidence beliefs are inherently protected from the sweep.
    count = 0
    for u in rows:
        if decay.should_tombstone(
            u.strength, u.decay_lambda, u.strength_updated_at, settings.tombstone_threshold, now
        ):
            u.status = "tombstoned"
            count += 1
    return count


async def compact(session: AsyncSession, *, tenant_id: str, retention_days: int = 30) -> int:
    cutoff = _now() - timedelta(days=retention_days)
    return await repository.hard_delete_tombstoned_before(
        session, tenant_id=tenant_id, cutoff=cutoff
    )


async def apply_dormancy_and_crystallize(
    session: AsyncSession, *, tenant_id: str, user_id: str, settings: Settings
) -> tuple[int, int]:
    """Drift dormant beliefs down, then crystallize high-confidence ones.

    Returns ``(crystallized, drifted)``.

    For each active semantic belief we first apply :func:`confidence.dormancy_drift`
    proportional to how many of the user's sessions have elapsed since the belief
    was last referenced (``last_retrieved_at`` falling back to ``created_at``).
    Drift happens *before* the crystallization check so a belief that has decayed
    in trust cannot be frozen on the same pass.
    """
    units = await repository.list_active_by_user(
        session, user_id=user_id, tenant_id=tenant_id, tier="semantic"
    )
    crystallized = 0
    drifted = 0
    for u in units:
        since = u.last_retrieved_at or u.created_at
        sessions_idle = await repository.count_sessions_since(
            session,
            user_id=user_id,
            tenant_id=tenant_id,
            since=since,
            exclude_session=u.last_referenced_session,
        )
        if sessions_idle > 0:
            new_conf = confidence.dormancy_drift(u.confidence, sessions_idle)
            if new_conf != u.confidence:
                u.confidence = new_conf
                drifted += 1

        if confidence.is_crystallized(u.confidence, settings.crystallize_threshold):
            # Freeze: mark crystallized and slow decay to the procedural rate.
            u.status = "crystallized"
            u.decay_lambda = settings.decay_lambda("procedural")
            crystallized += 1
    return crystallized, drifted


async def crystallize_procedural(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    *,
    tenant_id: str,
    user_id: str,
    settings: Settings,
    min_repeats: int = 3,
) -> int:
    """Extract repeated tool-call workflows into Tier-3 procedural memories."""
    runs = (
        await session.execute(
            select(AgentRun.run_id).where(
                AgentRun.tenant_id == tenant_id, AgentRun.user_id == user_id
            )
        )
    ).scalars().all()
    if not runs:
        return 0

    sequences: list[list[str]] = []
    for run_id in runs:
        calls = (
            await session.execute(
                select(ToolCall.tool_name)
                .where(ToolCall.run_id == run_id)
                .order_by(ToolCall.created_at)
            )
        ).scalars().all()
        if calls:
            sequences.append(list(calls))

    workflows = find_repeated_workflows(sequences, min_repeats=min_repeats)
    if not workflows:
        return 0

    # Avoid duplicating procedural memories already recorded.
    existing = {
        u.content
        for u in await repository.list_active_by_user(
            session, user_id=user_id, tenant_id=tenant_id, tier="procedural"
        )
    }

    created = 0
    for workflow, count in workflows:
        content = f"User repeatedly follows the workflow: {' -> '.join(workflow)} (seen {count}x)"
        if content in existing:
            continue
        emb = (await embedder.embed([content]))[0]
        await repository.insert_memory(
            session,
            user_id=user_id,
            tenant_id=tenant_id,
            tier="procedural",
            content=content,
            embedding=emb,
            decay_lambda=settings.decay_lambda("procedural"),
            confidence=0.8,
            scope="private",
            team_id=None,
            cluster="workflow",
            source_session_id=None,
        )
        created += 1
    return created


async def consolidate_user(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    *,
    tenant_id: str,
    user_id: str,
    settings: Settings | None = None,
    retention_days: int = 30,
) -> ConsolidationReport:
    """Run the full consolidation pass for one user."""
    settings = settings or get_settings()
    report = ConsolidationReport()
    report.crystallized_beliefs, report.dormant_drifted = await apply_dormancy_and_crystallize(
        session, tenant_id=tenant_id, user_id=user_id, settings=settings
    )
    report.procedural_created = await crystallize_procedural(
        session, embedder, tenant_id=tenant_id, user_id=user_id, settings=settings
    )
    report.tombstoned = await sweep_tombstones(session, tenant_id=tenant_id, settings=settings)
    report.compacted = await compact(session, tenant_id=tenant_id, retention_days=retention_days)
    log.info("consolidation.done", user_id=user_id, **report.__dict__)
    return report
