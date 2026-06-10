"""Unit tests for cross-session confidence accumulation."""

from __future__ import annotations

from recall.core import confidence


def test_corroboration_increases_with_diminishing_returns():
    first = confidence.corroborate(0.5, corroboration_count=0)
    second = confidence.corroborate(0.5, corroboration_count=4)
    assert first > 0.5
    # Later corroborations add less.
    assert (first - 0.5) > (second - 0.5)


def test_corroboration_clamps_at_one():
    assert confidence.corroborate(0.99, 0) <= 1.0


def test_contradiction_decreases_proportional_to_other_confidence():
    weak = confidence.contradict(0.8, contradicting_confidence=0.2)
    strong = confidence.contradict(0.8, contradicting_confidence=0.9)
    assert strong < weak < 0.8
    assert confidence.contradict(0.1, 0.9) >= 0.0


def test_dormancy_drifts_down():
    assert confidence.dormancy_drift(0.6, sessions_idle=5) < 0.6
    assert confidence.dormancy_drift(0.0, 10) == 0.0


def test_crystallization_threshold():
    assert confidence.is_crystallized(0.96, 0.95)
    assert not confidence.is_crystallized(0.94, 0.95)
