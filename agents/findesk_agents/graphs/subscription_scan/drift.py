"""Step-change detection — the silent price hike.

`anomaly_scan/detection.py` answers "is this bill an outlier?" with a ratio test
against a stable median. That is the right test for a one-off overcharge and the
wrong test for a subscription price rise, which is not an outlier at all: it is a
new level that persists. Measured against the real function, +12%, +20% and +24%
hikes are all invisible, and a +15% rise that has held for five months has been
absorbed into the baseline as the new normal.

So this is a changepoint detector, not a deviation detector. It looks for the
point where the series *level* shifts and stays shifted, and reports the annual
rupee consequence — which is the number a person can act on.

Do not fix the other detector by lowering its threshold: that would flood the
anomaly queue with ordinary variance and break a feature that works.

Pure and deterministic. NO LLM TOUCHES THIS MODULE.
"""

from __future__ import annotations

from statistics import median
from typing import Any

# Minimum sustained change worth reporting. 5% because real SaaS increases start
# around there; below it, ordinary rounding and FX noise dominate.
MIN_DRIFT = 0.05

# Each side of a candidate split needs this many charges before we will believe
# a level shift rather than a blip.
MIN_SIDE_POINTS = 2

# Each side must be internally stable, or "before" and "after" are not levels.
MAX_SIDE_SPREAD = 0.15

# Seat-creep: successive rises in near-equal discrete steps look like seats
# added, not a price change. Steps must agree within this tolerance.
SEAT_STEP_TOLERANCE = 0.2
MIN_SEAT_STEPS = 2


def _spread(values: list[int]) -> float:
    m = median(values)
    return (max(values) - min(values)) / m if m else float("inf")


def _stable(values: list[int]) -> bool:
    return len(values) >= MIN_SIDE_POINTS and _spread(values) <= MAX_SIDE_SPREAD


def detect_step_change(
    amounts: list[int], dates: list[str], *, min_drift: float = MIN_DRIFT
) -> dict[str, Any] | None:
    """The most significant sustained level shift in a series, or None.

    Scans every split point, keeps the one with the largest relative change
    where both sides are stable levels. Returns the change plus its annualizable
    per-period delta; callers multiply by periods_per_year.
    """
    n = len(amounts)
    if n < MIN_SIDE_POINTS * 2:
        return None

    best: dict[str, Any] | None = None
    for i in range(MIN_SIDE_POINTS, n - MIN_SIDE_POINTS + 1):
        before, after = amounts[:i], amounts[i:]
        if not _stable(before) or not _stable(after):
            continue
        b, a = int(median(before)), int(median(after))
        if b <= 0:
            continue
        pct = (a - b) / b
        if abs(pct) < min_drift:
            continue
        if best is None or abs(pct) > abs(best["pct"]):
            best = {
                "from_paise": b,
                "to_paise": a,
                "delta_paise": a - b,
                "pct": round(pct, 4),
                "direction": "increase" if pct > 0 else "decrease",
                "effective_from": dates[i],
                "points_before": len(before),
                "points_after": len(after),
            }
    return best


def detect_seat_creep(amounts: list[int]) -> dict[str, Any] | None:
    """Successive rises in near-equal steps — seats added, not a price hike.

    Matters because the action differs: a price rise is something to dispute or
    renegotiate, whereas seat growth is something to reconcile against headcount.
    Telling someone to "dispute the increase" when they hired three people is
    how a tool loses credibility.
    """
    rises = [
        (i, amounts[i] - amounts[i - 1])
        for i in range(1, len(amounts))
        if amounts[i] > amounts[i - 1]
    ]
    if len(rises) < MIN_SEAT_STEPS:
        return None
    steps = [d for _, d in rises]
    m = median(steps)
    if m <= 0:
        return None
    if any(abs(s - m) / m > SEAT_STEP_TOLERANCE for s in steps):
        return None
    # a run of equal-sized increases, never falling back
    return {
        "step_paise": int(m),
        "steps": len(steps),
        "total_paise": amounts[-1] - amounts[0],
        "from_paise": amounts[0],
        "to_paise": amounts[-1],
    }


def analyse(
    cadence: dict[str, Any], *, min_drift: float = MIN_DRIFT
) -> dict[str, Any]:
    """Drift verdict for one cadence-detected vendor.

    Skips `irregular` vendors entirely: usage-based billing has no level to
    shift, so every month would look like a step change. Those get reported in
    their own lane by the caller, never as a price hike.
    """
    amounts, dates = cadence["amounts"], cadence["dates"]
    if cadence["cadence"] == "irregular":
        return {
            "kind": "usage_based",
            "step_change": None,
            "seat_creep": None,
            "annualized_extra_paise": 0,
            "note": "Usage-based billing — amount varies by design, so a price "
            "change cannot be separated from a usage change.",
        }

    seat = detect_seat_creep(amounts)
    step = detect_step_change(amounts, dates, min_drift=min_drift)
    per_year = cadence.get("periods_per_year") or 0

    if seat is not None:
        return {
            "kind": "seat_creep",
            "step_change": None,
            "seat_creep": seat,
            "annualized_extra_paise": seat["total_paise"] * per_year,
            "note": (
                f"Rising in steps of about {seat['step_paise'] // 100:,} rupees "
                f"({seat['steps']} increases) — this looks like seats added "
                "rather than a price change."
            ),
        }
    if step is not None:
        extra = step["delta_paise"] * per_year
        return {
            "kind": "price_" + step["direction"],
            "step_change": step,
            "seat_creep": None,
            "annualized_extra_paise": extra,
            "note": (
                f"Price moved {step['pct'] * 100:+.1f}% from "
                f"{step['effective_from'][:10]} and stayed there."
            ),
        }
    return {
        "kind": "stable",
        "step_change": None,
        "seat_creep": None,
        "annualized_extra_paise": 0,
        "note": "No sustained price change detected.",
    }
