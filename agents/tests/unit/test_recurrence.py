"""Cadence detection — test vectors.

The detector decides whether something is a recurring commitment at all, so its
failure modes are asymmetric: a missed monthly series means a leak goes
unreported, while a false cadence on random spend means the tool nags about
nothing. Both get vectors.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from findesk_agents.graphs.subscription_scan.recurrence import (
    detect_all,
    detect_cadence,
)

NOW = datetime(2026, 7, 25, tzinfo=UTC)


def series(*, start: datetime, gap_days: int, n: int, amount: int = 100_000, gaps=None):
    """n charges from `start`, every `gap_days` (or an explicit gap list)."""
    dates, d = [], start
    for i in range(n):
        dates.append(d)
        d = d + timedelta(days=(gaps[i] if gaps and i < len(gaps) else gap_days))
    return [
        {
            "id": f"t{i}",
            "vendor_slug": "acme",
            "value_date": dt.isoformat(),
            "amount_paise": amount,
            "narration": "ACME SUBSCRIPTION",
            "counterparty_hint": "Acme",
            "category_code": "software_cloud",
        }
        for i, dt in enumerate(dates)
    ]


# --- the floor ------------------------------------------------------------


def test_two_charges_is_not_a_series():
    """Two points make an anecdote — detection.py already treats that as a
    possible duplicate."""
    assert detect_cadence(series(start=datetime(2026, 5, 1, tzinfo=UTC), gap_days=30, n=2),
                          now=NOW) is None


def test_same_day_repeats_are_not_a_cadence():
    txns = series(start=datetime(2026, 7, 1, tzinfo=UTC), gap_days=0, n=4)
    assert detect_cadence(txns, now=NOW) is None


# --- clean cadences -------------------------------------------------------


def test_monthly_series_is_detected():
    v = detect_cadence(series(start=datetime(2026, 2, 5, tzinfo=UTC), gap_days=30, n=6), now=NOW)
    assert v["cadence"] == "monthly"
    assert v["periods_per_year"] == 12
    assert v["occurrences"] == 6
    assert v["status"] == "active"


def test_month_length_variation_is_still_monthly():
    """28/31/30/31-day gaps are one cadence, not four. An absolute tolerance is
    the whole reason CADENCES carries days rather than a ratio."""
    v = detect_cadence(
        series(start=datetime(2026, 1, 31, tzinfo=UTC), gap_days=30, n=6,
               gaps=[28, 31, 30, 31, 30]),
        now=NOW,
    )
    assert v["cadence"] == "monthly"


def test_weekly_quarterly_and_annual():
    w = detect_cadence(series(start=datetime(2026, 5, 1, tzinfo=UTC), gap_days=7, n=8), now=NOW)
    q = detect_cadence(series(start=datetime(2025, 8, 1, tzinfo=UTC), gap_days=91, n=4), now=NOW)
    a = detect_cadence(series(start=datetime(2023, 7, 1, tzinfo=UTC), gap_days=365, n=3), now=NOW)
    assert (w["cadence"], q["cadence"], a["cadence"]) == ("weekly", "quarterly", "annual")
    assert (w["periods_per_year"], q["periods_per_year"], a["periods_per_year"]) == (52, 4, 1)


# --- the skipped-period case ---------------------------------------------


def test_one_skipped_month_still_reads_as_monthly():
    """A ~60-day gap is one missed charge. Without normalization it doubles the
    median and destroys an obvious monthly series."""
    v = detect_cadence(
        series(start=datetime(2026, 1, 5, tzinfo=UTC), gap_days=30, n=6,
               gaps=[30, 30, 60, 30, 30]),
        now=NOW,
    )
    assert v["cadence"] == "monthly", f"got {v['cadence']} (period {v['period_days']})"


# --- irregular / usage-based ---------------------------------------------


def test_wildly_irregular_gaps_are_not_given_a_cadence():
    v = detect_cadence(
        series(start=datetime(2026, 1, 5, tzinfo=UTC), gap_days=30, n=6,
               gaps=[3, 47, 9, 61, 5]),
        now=NOW,
    )
    assert v["cadence"] == "irregular"
    assert v["periods_per_year"] is None
    assert v["confidence"] <= 0.3


def test_usage_based_amounts_do_not_break_a_regular_cadence():
    """AWS bills monthly but the amount swings. Cadence is about DATES —
    varying amounts must not downgrade it (drift.py handles the amounts)."""
    txns = series(start=datetime(2026, 2, 5, tzinfo=UTC), gap_days=30, n=6)
    for i, amt in enumerate([80_000, 210_000, 95_000, 340_000, 120_000, 260_000]):
        txns[i]["amount_paise"] = amt
    v = detect_cadence(txns, now=NOW)
    assert v["cadence"] == "monthly"


# --- lifecycle ------------------------------------------------------------


def test_a_stopped_series_is_marked_stopped():
    """Last charge 4 months ago on a monthly cadence — already cancelled."""
    v = detect_cadence(
        series(start=datetime(2025, 11, 1, tzinfo=UTC), gap_days=30, n=5), now=NOW
    )
    assert v["status"] == "stopped"
    assert v["days_until_next"] < 0


def test_a_slightly_late_charge_is_not_stopped():
    """Grace exists so a bill three days late doesn't read as a cancellation."""
    start = NOW - timedelta(days=30 * 4 + 3)
    v = detect_cadence(series(start=start, gap_days=30, n=5), now=NOW)
    assert v["status"] == "active", f"days_until_next={v['days_until_next']}"


def test_next_expected_supports_a_pre_renewal_prompt():
    """An annual renewal you can see coming is the only kind you can act on."""
    # three annual charges, the newest ~345 days ago → renewal ~20 days out
    start = NOW - timedelta(days=365 * 3 - 20)
    v = detect_cadence(series(start=start, gap_days=365, n=3), now=NOW)
    assert v["cadence"] == "annual"
    assert v["status"] == "active", "an annual series is not stopped at 345 days"
    assert 0 < v["days_until_next"] <= 60


# --- confidence & rollup -------------------------------------------------


def test_more_charges_means_more_confidence():
    few = detect_cadence(
        series(start=datetime(2026, 4, 5, tzinfo=UTC), gap_days=30, n=3), now=NOW
    )
    many = detect_cadence(
        series(start=datetime(2025, 9, 5, tzinfo=UTC), gap_days=30, n=10), now=NOW
    )
    assert many["confidence"] > few["confidence"]


def test_detect_all_drops_vendors_below_the_floor():
    a = series(start=datetime(2026, 2, 5, tzinfo=UTC), gap_days=30, n=6)
    b = series(start=datetime(2026, 6, 1, tzinfo=UTC), gap_days=30, n=2)
    for t in b:
        t["vendor_slug"] = "onlytwice"
    found = detect_all(a + b, now=NOW)
    assert set(found) == {"acme"}
    assert found["acme"]["vendor_label"] == "Acme"
    assert found["acme"]["category_code"] == "software_cloud"


def test_median_amount_is_representative_not_the_latest():
    """A hike in the newest charge must not silently become 'the' price."""
    txns = series(start=datetime(2026, 2, 5, tzinfo=UTC), gap_days=30, n=6)
    txns[-1]["amount_paise"] = 500_000
    v = detect_cadence(txns, now=NOW)
    assert v["amount_paise"] == 100_000
    assert v["latest_amount_paise"] == 500_000
