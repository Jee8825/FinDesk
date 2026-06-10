"""Mathematical memory decay with retrieval reinforcement.

This is Recall's core differentiator. Memory *strength* is a continuously
decaying value following an Ebbinghaus-style forgetting curve:

    S(t) = S0 * exp(-lambda * t)

where ``t`` is elapsed time in days and ``lambda`` differs per tier (episodic
forgets in days, semantic in weeks, procedural almost never). Every retrieval
multiplies the *current* strength by a reinforcement factor ``r > 1`` (capped at
1.0 to keep the scale normalized) and resets the decay clock. Memories whose
current strength falls below threshold ``tau`` are tombstoned (soft-deleted).

All functions here are pure so they can be unit-tested without a database.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

SECONDS_PER_DAY = 86_400.0
MAX_STRENGTH = 1.0


def elapsed_days(since: datetime, now: datetime | None = None) -> float:
    """Elapsed time in (fractional) days between ``since`` and ``now``."""
    now = now or datetime.now(UTC)
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    return max(0.0, (now - since).total_seconds() / SECONDS_PER_DAY)


def current_strength(
    stored_strength: float,
    decay_lambda: float,
    strength_updated_at: datetime,
    now: datetime | None = None,
) -> float:
    """Return the decayed strength at ``now`` given the last materialized value."""
    dt = elapsed_days(strength_updated_at, now)
    return stored_strength * math.exp(-decay_lambda * dt)


def reinforce(
    stored_strength: float,
    decay_lambda: float,
    strength_updated_at: datetime,
    reinforcement_factor: float,
    now: datetime | None = None,
) -> float:
    """Return the new stored strength after a retrieval reinforcement.

    The decayed current strength is boosted by ``reinforcement_factor`` and
    clamped to ``MAX_STRENGTH``. Callers persist this together with a refreshed
    ``strength_updated_at = now``.
    """
    decayed = current_strength(stored_strength, decay_lambda, strength_updated_at, now)
    return min(MAX_STRENGTH, decayed * reinforcement_factor)


def should_tombstone(
    stored_strength: float,
    decay_lambda: float,
    strength_updated_at: datetime,
    tombstone_threshold: float,
    now: datetime | None = None,
) -> bool:
    """True if the memory has decayed below the soft-delete threshold."""
    return current_strength(stored_strength, decay_lambda, strength_updated_at, now) < (
        tombstone_threshold
    )


def half_life_days(decay_lambda: float) -> float:
    """Convenience: the half-life implied by a decay constant (ln 2 / lambda)."""
    if decay_lambda <= 0:
        return math.inf
    return math.log(2) / decay_lambda
