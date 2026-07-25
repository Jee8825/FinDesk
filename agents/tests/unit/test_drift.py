"""Step-change detection — test vectors.

The first block is the point of the whole module: the cases anomaly_scan
provably cannot see. Those are asserted against BOTH detectors so the gap is
documented in executable form, not just prose.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from findesk_agents.graphs.anomaly_scan.detection import detect_deviations
from findesk_agents.graphs.subscription_scan.drift import (
    analyse,
    detect_seat_creep,
    detect_step_change,
)
from findesk_agents.graphs.subscription_scan.recurrence import detect_cadence

NOW = datetime(2026, 7, 25, tzinfo=UTC)


def _series(amounts, *, gap_days=30, vendor="acme"):
    start = NOW - timedelta(days=gap_days * len(amounts))
    return [
        {
            "id": f"t{i}",
            "vendor_slug": vendor,
            "value_date": (start + timedelta(days=gap_days * i)).isoformat(),
            "amount_paise": a,
            "narration": "ACME SUBSCRIPTION",
            "counterparty_hint": "Acme",
            "category_code": "software_cloud",
        }
        for i, a in enumerate(amounts)
    ]


def _dates(n, gap_days=30):
    start = NOW - timedelta(days=gap_days * n)
    return [(start + timedelta(days=gap_days * i)).isoformat() for i in range(n)]


def _drift(amounts):
    return detect_step_change(amounts, _dates(len(amounts)))


# --- the gap this module exists to close ---------------------------------


def test_catches_the_hikes_the_anomaly_detector_misses():
    """+12%/+20%/+24% are invisible to a ratio test against a stable median.
    A changepoint test sees all of them."""
    for pct in (0.12, 0.20, 0.24):
        amounts = [100_000] * 6 + [int(100_000 * (1 + pct))] * 3
        assert detect_deviations(_series(amounts)) == [], (
            f"anomaly_scan unexpectedly caught +{pct:.0%} — update this test"
        )
        step = _drift(amounts)
        assert step is not None, f"drift.py must catch +{pct:.0%}"
        assert step["direction"] == "increase"
        assert abs(step["pct"] - pct) < 0.01


def test_catches_a_hike_that_has_already_become_the_new_normal():
    """The worst case: a +15% rise held for five months. The old detector has
    absorbed it into the baseline; the changepoint is still there."""
    amounts = [100_000] * 6 + [115_000] * 5
    assert detect_deviations(_series(amounts)) == []
    step = _drift(amounts)
    assert step is not None
    assert step["from_paise"] == 100_000
    assert step["to_paise"] == 115_000


# --- basic behaviour ------------------------------------------------------


def test_flat_series_has_no_drift():
    assert _drift([100_000] * 8) is None


def test_change_below_the_floor_is_ignored():
    """3% is rounding and FX noise, not a price decision."""
    assert _drift([100_000] * 5 + [103_000] * 4) is None


def test_reports_the_date_the_new_price_took_effect():
    amounts = [100_000] * 4 + [130_000] * 4
    step = _drift(amounts)
    assert step["effective_from"] == _dates(8)[4]


def test_detects_a_decrease_too():
    step = _drift([200_000] * 4 + [150_000] * 4)
    assert step["direction"] == "decrease"
    assert step["pct"] < 0


def test_a_single_spike_is_not_a_step_change():
    """One bad month is anomaly_scan's job. A level shift must persist."""
    assert _drift([100_000] * 5 + [400_000] + [100_000] * 3) is None


def test_needs_enough_points_on_both_sides():
    assert _drift([100_000, 150_000]) is None
    assert _drift([100_000, 100_000, 150_000]) is None


def test_picks_the_largest_shift_when_there_are_two():
    step = _drift([100_000] * 3 + [110_000] * 3 + [200_000] * 3)
    assert step["to_paise"] == 200_000, "should report the dominant change"


# --- seat creep -----------------------------------------------------------


def test_equal_steps_read_as_seat_creep_not_a_price_hike():
    seat = detect_seat_creep([100_000, 150_000, 200_000, 250_000])
    assert seat is not None
    assert seat["step_paise"] == 50_000
    assert seat["steps"] == 3


def test_a_single_jump_is_not_seat_creep():
    assert detect_seat_creep([100_000, 100_000, 150_000, 150_000]) is None


def test_uneven_rises_are_not_seat_creep():
    assert detect_seat_creep([100_000, 130_000, 190_000, 400_000]) is None


# --- the combined verdict -------------------------------------------------


def test_analyse_annualizes_a_monthly_hike():
    cadence = detect_cadence(_series([100_000] * 6 + [115_000] * 3), now=NOW)
    out = analyse(cadence)
    assert out["kind"] == "price_increase"
    # ₹150/month extra × 12 = ₹1,800/year
    assert out["annualized_extra_paise"] == 15_000 * 12
    assert "stayed there" in out["note"]


def test_analyse_prefers_the_seat_creep_explanation():
    """When both fire, the action differs — don't tell someone to dispute an
    increase they caused by hiring."""
    cadence = detect_cadence(_series([100_000, 150_000, 200_000, 250_000]), now=NOW)
    out = analyse(cadence)
    assert out["kind"] == "seat_creep"
    assert "seats added" in out["note"]


def test_analyse_excludes_usage_based_vendors_from_drift():
    """AWS varies every month by design; calling that a price hike monthly is
    how a detector gets ignored."""
    cadence = detect_cadence(
        _series([80_000, 210_000, 95_000, 340_000, 120_000], gap_days=13), now=NOW
    )
    cadence["cadence"] = "irregular"
    cadence["periods_per_year"] = None
    out = analyse(cadence)
    assert out["kind"] == "usage_based"
    assert out["annualized_extra_paise"] == 0
    assert out["step_change"] is None


def test_analyse_reports_stable_when_nothing_moved():
    cadence = detect_cadence(_series([100_000] * 6), now=NOW)
    out = analyse(cadence)
    assert out["kind"] == "stable"
    assert out["annualized_extra_paise"] == 0
