"""Unit tests for procedural workflow detection (pure)."""

from __future__ import annotations

from recall.core.consolidation import find_repeated_workflows


def test_detects_repeated_workflow():
    runs = [
        ["search", "open", "edit", "save"],
        ["search", "open", "edit", "save"],
        ["search", "open", "edit", "save"],
        ["unrelated"],
    ]
    workflows = find_repeated_workflows(runs, min_len=2, min_repeats=3)
    grams = [w for w, _ in workflows]
    # The full 4-step workflow should be detected (subsumes shorter ones).
    assert ("search", "open", "edit", "save") in grams


def test_ignores_below_repeat_threshold():
    runs = [["a", "b"], ["a", "b"]]  # only twice
    assert find_repeated_workflows(runs, min_len=2, min_repeats=3) == []


def test_subsumed_shorter_patterns_dropped():
    runs = [["x", "y", "z"]] * 3
    workflows = find_repeated_workflows(runs, min_len=2, min_repeats=3)
    grams = [w for w, _ in workflows]
    assert ("x", "y", "z") in grams
    # The 2-grams are subsumed by the 3-gram (same count) and dropped.
    assert ("x", "y") not in grams
