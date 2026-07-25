"""IMS deemed-acceptance clock — test vectors.

Statutory arithmetic gets vectors, not smoke tests: a wrong deadline here does
not throw, it quietly tells an SME they have time they do not have, and the
consequence (a deemed-accepted invoice under a hard-locked GSTR-3B Table 4) is
not correctable on their own return.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.statutory import (
    gstr3b_due,
    ims_clock_snapshot,
    ims_deemed_accept_at,
    ims_urgency,
    parse_period,
    quarter_end_month,
)

# --- period parsing -------------------------------------------------------


def test_parse_period():
    assert parse_period("2026-07") == (2026, 7)
    assert parse_period("2026-12") == (2026, 12)


@pytest.mark.parametrize("bad", ["2026-13", "2026-00"])
def test_parse_period_rejects_impossible_months(bad):
    with pytest.raises(ValueError):
        parse_period(bad)


# --- GST quarters follow Apr-Jun / Jul-Sep / Oct-Dec / Jan-Mar ------------


@pytest.mark.parametrize(
    ("month", "expected"),
    [(1, 3), (2, 3), (3, 3), (4, 6), (5, 6), (6, 6),
     (7, 9), (8, 9), (9, 9), (10, 12), (11, 12), (12, 12)],
)
def test_quarter_end_month(month, expected):
    assert quarter_end_month(month) == expected


# --- GSTR-3B due dates ----------------------------------------------------


def test_monthly_3b_is_due_on_the_20th_of_the_following_month():
    assert gstr3b_due("2026-07", frequency="monthly") == datetime(2026, 8, 20, tzinfo=UTC)


def test_monthly_3b_rolls_the_year():
    assert gstr3b_due("2026-12", frequency="monthly") == datetime(2027, 1, 20, tzinfo=UTC)


def test_quarterly_3b_is_due_after_the_quarter_ends():
    # Jul-Sep quarter → 22nd of the month after September
    for period in ("2026-07", "2026-08", "2026-09"):
        assert gstr3b_due(period, frequency="quarterly") == datetime(2026, 10, 22, tzinfo=UTC)


def test_unknown_frequency_is_rejected_rather_than_guessed():
    with pytest.raises(ValueError):
        gstr3b_due("2026-07", frequency="annual")


# --- the deemed-acceptance deadline: one tax period of grace --------------


def test_monthly_record_is_deemed_accepted_two_months_out():
    """A July record may sit pending through August; the August 3B due date
    (20 Sep) is the wall."""
    assert ims_deemed_accept_at("2026-07", frequency="monthly") == datetime(
        2026, 9, 20, tzinfo=UTC
    )


def test_monthly_deadline_crosses_the_year_boundary():
    assert ims_deemed_accept_at("2026-11", frequency="monthly") == datetime(
        2027, 1, 20, tzinfo=UTC
    )
    assert ims_deemed_accept_at("2026-12", frequency="monthly") == datetime(
        2027, 2, 20, tzinfo=UTC
    )


def test_every_month_of_a_quarter_shares_one_deadline():
    """QRMP grace is a whole quarter, so Jul/Aug/Sep records all lapse together
    on the Oct-Dec 3B due date."""
    deadlines = {
        ims_deemed_accept_at(p, frequency="quarterly")
        for p in ("2026-07", "2026-08", "2026-09")
    }
    assert deadlines == {datetime(2027, 1, 22, tzinfo=UTC)}


def test_quarterly_grace_is_strictly_longer_than_monthly():
    monthly = ims_deemed_accept_at("2026-07", frequency="monthly")
    quarterly = ims_deemed_accept_at("2026-07", frequency="quarterly")
    assert quarterly > monthly, "QRMP filers get a quarter, not a month"


# --- urgency bands --------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "band"),
    [(90, "safe"), (31, "safe"), (30, "due_soon"), (8, "due_soon"),
     (7, "urgent"), (1, "urgent"), (0, "urgent"), (-1, "lapsed"), (-40, "lapsed")],
)
def test_urgency_bands(days, band):
    assert ims_urgency(days) == band


def test_deadline_day_itself_is_urgent_not_lapsed():
    """Action is still possible on the due date — do not tell a user it is over."""
    assert ims_urgency(0) == "urgent"


# --- the row payload ------------------------------------------------------


def test_snapshot_counts_down_and_holds_itc_at_risk():
    snap = ims_clock_snapshot(
        period="2026-07",
        now=datetime(2026, 9, 15, tzinfo=UTC),
        frequency="monthly",
        tax_paise=450_000,
    )
    assert snap["deemed_accept_at"] == datetime(2026, 9, 20, tzinfo=UTC).isoformat()
    assert snap["days_remaining"] == 5
    assert snap["urgency"] == "urgent"
    assert snap["itc_at_risk_paise"] == 450_000
    assert snap["itc_deemed_paise"] == 0


def test_snapshot_after_the_deadline_reports_the_credit_as_taken():
    """Past the wall the ITC is no longer 'at risk' — it has been decided."""
    snap = ims_clock_snapshot(
        period="2026-07",
        now=datetime(2026, 9, 21, tzinfo=UTC),
        frequency="monthly",
        tax_paise=450_000,
    )
    assert snap["days_remaining"] == -1
    assert snap["urgency"] == "lapsed"
    assert snap["itc_at_risk_paise"] == 0
    assert snap["itc_deemed_paise"] == 450_000


def test_snapshot_is_day_granular_not_time_sensitive():
    """Two moments on the same day must not disagree about days remaining."""
    early = ims_clock_snapshot(
        period="2026-07", now=datetime(2026, 9, 15, 0, 1, tzinfo=UTC), frequency="monthly"
    )
    late = ims_clock_snapshot(
        period="2026-07", now=datetime(2026, 9, 15, 23, 59, tzinfo=UTC), frequency="monthly"
    )
    assert early["days_remaining"] == late["days_remaining"]
