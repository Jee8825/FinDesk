"""Cadence detection — is this vendor a recurring commitment, and how often?

The gap the anomaly scan never filled. `detection.py` infers "recurring" from
*amount stability* (a stable median); this infers it from *periodicity* (regular
inter-arrival gaps). They disagree in both directions, and both directions
matter: two identical charges three days apart are stable but not recurring; a
usage-based cloud bill every month is recurring but not stable.

Pure and deterministic. NO LLM TOUCHES THIS MODULE — payee canonicalization
happens upstream, so by the time series reach here the grouping is already
decided.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Any

# A series needs three charges before we will call it recurring: two gaps, so a
# claim about regularity can at least be contradicted. Two charges is an
# anecdote — `detection.py` already handles that case as a possible duplicate.
MIN_OCCURRENCES = 3
CONFIDENT_OCCURRENCES = 4

# (label, expected days, tolerance days). Monthly needs an ABSOLUTE tolerance,
# not a relative one: real billing drifts across weekends and unequal month
# lengths, so 28-31 days is one cadence, not four.
CADENCES = (
    ("weekly", 7, 2),
    ("fortnightly", 14, 3),
    ("monthly", 30, 5),
    ("quarterly", 91, 12),
    ("annual", 365, 30),
)

PERIODS_PER_YEAR = {
    "weekly": 52,
    "fortnightly": 26,
    "monthly": 12,
    "quarterly": 4,
    "annual": 1,
}

# How far past the next expected charge before a series counts as stopped.
# Generous on purpose: nagging someone about a subscription they already
# cancelled is the fastest way to lose their trust in the whole tool.
STOPPED_GRACE_MULTIPLIER = 1.5
STOPPED_GRACE_MIN_DAYS = 10

# Max relative dispersion of normalized gaps for a cadence to be believed.
MAX_GAP_DISPERSION = 0.25


def _date(txn: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(txn["value_date"])


def _normalized_gaps(gaps: list[int], base: float) -> list[float]:
    """Divide each gap by the number of periods it spans.

    A monthly series with one skipped charge produces a ~60-day gap. Without
    this, that single miss doubles the median and destroys an obvious monthly
    cadence. Dividing by round(gap/base) treats it as one missed period, which
    is what it is.
    """
    out = []
    for g in gaps:
        periods = max(1, round(g / base)) if base > 0 else 1
        out.append(g / periods)
    return out


def _classify(period_days: float) -> tuple[str | None, int | None]:
    for label, expected, tol in CADENCES:
        if abs(period_days - expected) <= tol:
            return label, expected
    return None, None


DUPLICATE_COLLAPSE_DAYS = 5


def collapse_duplicates(txns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Treat a same-amount re-charge within a few days as ONE billing event.

    Cadence is a property of the billing cycle, not of the charge count. A
    monthly vendor that double-billed once produces a 3-day gap among 30-day
    gaps, which drags the series into `irregular` and suppresses drift detection
    on a vendor that is perfectly regular. The duplicate itself is not lost —
    `anomaly_scan.detect_duplicates` reports it, and scoring counts it as
    recoverable.
    """
    ordered = sorted(txns, key=_date)
    kept: list[dict[str, Any]] = []
    for t in ordered:
        if kept:
            prev = kept[-1]
            same_amount = prev["amount_paise"] == t["amount_paise"]
            close = (_date(t) - _date(prev)).days <= DUPLICATE_COLLAPSE_DAYS
            if same_amount and close:
                continue
        kept.append(t)
    return kept


def detect_cadence(txns: list[dict[str, Any]], *, now: datetime) -> dict[str, Any] | None:
    """One vendor's series → cadence verdict, or None if it isn't a series.

    Returns a dict with cadence, period_days, occurrences, confidence,
    first_seen/last_seen, next_expected, status (active|stopped) and the
    representative amount. ``cadence="irregular"`` means the charges repeat but
    not on a rhythm we will stand behind — usage-based billing lands here, and
    drift detection must skip it.
    """
    if len(txns) < MIN_OCCURRENCES:
        return None

    ordered = collapse_duplicates(txns)
    if len(ordered) < MIN_OCCURRENCES:
        return None
    dates = [_date(t) for t in ordered]
    gaps = [(b - a).days for a, b in zip(dates, dates[1:], strict=False)]
    if not gaps or all(g == 0 for g in gaps):
        return None  # same-day repeats are duplicates, not a cadence

    raw_median = median(gaps)
    normalized = _normalized_gaps(gaps, raw_median)
    period_days = median(normalized)
    if period_days <= 0:
        return None

    spread = (max(normalized) - min(normalized)) / period_days
    label, expected = _classify(period_days)
    if label is None or spread > MAX_GAP_DISPERSION:
        cadence, periods_year = "irregular", None
    else:
        cadence, periods_year = label, PERIODS_PER_YEAR[label]

    amounts = [t["amount_paise"] for t in ordered]
    last_seen = dates[-1]
    next_expected = last_seen + timedelta(days=round(period_days))
    grace = max(STOPPED_GRACE_MIN_DAYS, round(period_days * (STOPPED_GRACE_MULTIPLIER - 1)))
    stopped = now > next_expected + timedelta(days=grace)

    return {
        "cadence": cadence,
        "period_days": round(period_days, 1),
        "periods_per_year": periods_year,
        "occurrences": len(ordered),
        "confidence": _confidence(len(ordered), spread, cadence),
        "gap_dispersion": round(spread, 3),
        "first_seen": dates[0].isoformat(),
        "last_seen": last_seen.isoformat(),
        "next_expected": next_expected.isoformat(),
        "days_until_next": (next_expected.date() - now.date()).days,
        "status": "stopped" if stopped else "active",
        "amount_paise": int(median(amounts)),
        "latest_amount_paise": amounts[-1],
        "amounts": amounts,
        "dates": [d.isoformat() for d in dates],
    }


def _confidence(occurrences: int, spread: float, cadence: str) -> float:
    """0..1, deterministic. More charges and tighter gaps mean more confidence."""
    if cadence == "irregular":
        return 0.3 if occurrences >= CONFIDENT_OCCURRENCES else 0.2
    base = 0.6 if occurrences < CONFIDENT_OCCURRENCES else 0.85
    tightness = max(0.0, 1 - (spread / MAX_GAP_DISPERSION))
    return round(min(1.0, base + 0.15 * tightness), 2)


def group_by_vendor(
    debits: list[dict[str, Any]], *, key: str = "vendor_slug"
) -> dict[str, list[dict[str, Any]]]:
    """Bucket debits by their (already canonicalized) vendor key."""
    out: dict[str, list[dict[str, Any]]] = {}
    for t in debits:
        out.setdefault(t[key], []).append(t)
    return out


def detect_all(
    debits: list[dict[str, Any]], *, now: datetime, key: str = "vendor_slug"
) -> dict[str, dict[str, Any]]:
    """Every vendor with a detectable cadence. Vendors below the floor drop out."""
    found = {}
    for vendor, txns in group_by_vendor(debits, key=key).items():
        verdict = detect_cadence(txns, now=now)
        if verdict is not None:
            verdict["vendor_slug"] = vendor
            verdict["vendor_label"] = (
                txns[0].get("counterparty_hint") or txns[0].get("narration", "")[:40]
            )
            verdict["category_code"] = txns[0].get("category_code")
            found[vendor] = verdict
    return found
