"""Unit tests for conflict-detection geometry (cosine distance + nearest)."""

from __future__ import annotations

from datetime import UTC, datetime

from recall.core import conflict
from recall.db.models import MemoryUnit


def _unit(embedding: list[float]) -> MemoryUnit:
    u = MemoryUnit(
        user_id="u1",
        tier="semantic",
        content="x",
        embedding=embedding,
        decay_lambda=0.02,
        confidence=0.6,
        strength=1.0,
        strength_updated_at=datetime.now(UTC),
    )
    return u


def test_cosine_distance_identical_is_zero():
    assert abs(conflict.cosine_distance([1.0, 0.0], [1.0, 0.0])) < 1e-9


def test_cosine_distance_orthogonal_is_one():
    assert abs(conflict.cosine_distance([1.0, 0.0], [0.0, 1.0]) - 1.0) < 1e-9


def test_find_nearest_returns_closest_within_threshold():
    new = [1.0, 0.0]
    near = _unit([0.99, 0.14])  # small distance
    far = _unit([0.0, 1.0])  # orthogonal
    result = conflict.find_nearest(new, [far, near], threshold=0.25)
    assert result is not None
    assert result[0] is near


def test_find_nearest_returns_none_when_all_far():
    result = conflict.find_nearest([1.0, 0.0], [_unit([0.0, 1.0])], threshold=0.25)
    assert result is None


def test_find_nearest_skips_tombstoned_candidates():
    # A belief retired earlier in the same ingest batch must not be matched.
    new = [1.0, 0.0]
    retired = _unit([0.99, 0.14])
    retired.status = "tombstoned"
    assert conflict.find_nearest(new, [retired], threshold=0.25) is None
    # An active near belief is still matched.
    active = _unit([0.99, 0.14])
    active.status = "active"
    assert conflict.find_nearest(new, [active], threshold=0.25) is not None
