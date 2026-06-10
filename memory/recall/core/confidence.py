"""Cross-session confidence accumulation.

Confidence is the epistemic axis — how much the agent should *trust* a belief,
orthogonal to strength (retrieval priority). It evolves across sessions by four
rules:

* corroboration  — a new session restates the fact: ``+delta`` with diminishing
  returns (prevents runaway inflation).
* contradiction  — a conflicting fact appears: ``-delta`` proportional to the
  contradicting belief's own confidence.
* dormancy       — unreferenced for several sessions: a slow downward drift.
* crystallization— once confidence exceeds a threshold the belief is "known";
  decay is paused and drift stops.

All functions are pure and clamp to [0, 1].
"""

from __future__ import annotations

_CORROBORATION_BASE = 0.15
_CONTRADICTION_K = 0.5
_DORMANCY_DRIFT = 0.02


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def corroborate(confidence: float, corroboration_count: int) -> float:
    """Increase confidence with diminishing returns (saturates after ~5 repeats)."""
    delta = _CORROBORATION_BASE / (1 + corroboration_count)
    return _clamp(confidence + delta)


def contradict(confidence: float, contradicting_confidence: float) -> float:
    """Decrease confidence in proportion to the contradicting belief's confidence."""
    return _clamp(confidence - _CONTRADICTION_K * contradicting_confidence)


def dormancy_drift(confidence: float, sessions_idle: int) -> float:
    """Apply slow downward drift for prolonged non-reference."""
    return _clamp(confidence - _DORMANCY_DRIFT * sessions_idle)


def is_crystallized(confidence: float, threshold: float) -> bool:
    return confidence >= threshold
