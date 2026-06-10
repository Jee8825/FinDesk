"""Unit tests for the decay engine (pure math, no datastore)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from recall.core import decay


def _ago(days: float) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


def test_strength_decays_over_time():
    lam = 0.35
    s0 = 1.0
    one_day = decay.current_strength(s0, lam, _ago(1))
    ten_days = decay.current_strength(s0, lam, _ago(10))
    assert one_day < s0
    assert ten_days < one_day
    assert math.isclose(decay.current_strength(s0, lam, _ago(0)), s0, rel_tol=1e-3)


def test_decay_matches_closed_form():
    lam = 0.2
    val = decay.current_strength(1.0, lam, _ago(5))
    assert math.isclose(val, math.exp(-lam * 5), rel_tol=1e-3)


def test_procedural_decays_slower_than_episodic():
    epi = decay.current_strength(1.0, 0.35, _ago(7))
    proc = decay.current_strength(1.0, 0.001, _ago(7))
    assert proc > epi


def test_reinforce_boosts_but_caps_at_one():
    # A decayed memory gets boosted back up.
    boosted = decay.reinforce(1.0, 0.35, _ago(5), reinforcement_factor=1.25)
    decayed = decay.current_strength(1.0, 0.35, _ago(5))
    assert boosted > decayed
    assert boosted <= decay.MAX_STRENGTH
    # A fresh memory cannot exceed the cap.
    assert decay.reinforce(1.0, 0.35, _ago(0), 1.25) == decay.MAX_STRENGTH


def test_tombstone_when_below_threshold():
    # After long enough, episodic strength drops under tau.
    assert decay.should_tombstone(1.0, 0.35, _ago(60), tombstone_threshold=0.05)
    assert not decay.should_tombstone(1.0, 0.001, _ago(60), tombstone_threshold=0.05)


def test_half_life():
    assert math.isclose(decay.half_life_days(0.35), math.log(2) / 0.35, rel_tol=1e-6)
    assert decay.half_life_days(0.0) == math.inf
