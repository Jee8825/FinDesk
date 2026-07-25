"""IMS deemed-acceptance rollup + the close-checklist consequence.

The engine's vectors live in test_statutory_ims.py. This covers the two places
the clock changes behaviour: what the /ims queue reports, and when an
un-actioned queue stops being a warning and starts blocking sign-off.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.services.close import ims_check_value, ims_severity
from app.services.ims import itc_clock_rollup

NOW = datetime(2026, 9, 1, tzinfo=UTC)  # July period lapses 20 Sep → 19 days out


@dataclass
class Row:
    state: str = "pending"
    period: str = "2026-07"
    tax_paise: int = 100_000


def _rollup(rows, frequency="monthly", now=NOW):
    return itc_clock_rollup(rows, frequency=frequency, now=now)


# --- rollup ---------------------------------------------------------------


def test_empty_queue_is_safe_and_names_the_frequency():
    out = _rollup([])
    assert out["urgency"] == "safe"
    assert out["next_deadline"] is None
    assert out["itc_at_risk_paise"] == 0
    assert out["filing_frequency"] == "monthly"


def test_decided_records_carry_no_clock():
    """Accepted/rejected rows are done — they must not inflate ITC at risk."""
    out = _rollup([Row(state="accepted"), Row(state="rejected")])
    assert out["itc_at_risk_paise"] == 0
    assert out["next_deadline"] is None


def test_pending_records_sum_the_credit_at_risk():
    out = _rollup([Row(tax_paise=100_000), Row(tax_paise=250_000)])
    assert out["itc_at_risk_paise"] == 350_000
    assert out["days_remaining"] == 19
    assert out["urgency"] == "due_soon"


def test_queue_is_as_urgent_as_its_most_urgent_row():
    """A comfortable average must never mask one record about to lapse."""
    out = _rollup(
        [Row(period="2026-08"), Row(period="2026-07")],
        now=datetime(2026, 9, 18, tzinfo=UTC),
    )
    assert out["urgency"] == "urgent", "the July row lapses in 2 days"
    assert out["days_remaining"] == 2
    assert out["next_deadline"].startswith("2026-09-20")


def test_lapsed_credit_moves_out_of_at_risk_into_lapsed():
    out = _rollup([Row(period="2026-07", tax_paise=90_000)], now=datetime(2026, 9, 25, tzinfo=UTC))
    assert out["urgency"] == "lapsed"
    assert out["itc_at_risk_paise"] == 0
    assert out["itc_lapsed_paise"] == 90_000
    assert out["lapsed_count"] == 1


def test_lapsing_soon_counts_only_the_urgent_band():
    rows = [Row(period="2026-07", tax_paise=50_000), Row(period="2026-08", tax_paise=70_000)]
    out = _rollup(rows, now=datetime(2026, 9, 18, tzinfo=UTC))
    assert out["lapsing_soon_paise"] == 50_000, "the August row still has a month"


def test_quarterly_filers_get_a_longer_runway():
    rows = [Row(period="2026-07")]
    assert _rollup(rows, frequency="monthly")["days_remaining"] == 19
    assert _rollup(rows, frequency="quarterly")["days_remaining"] > 19


# --- close-checklist consequence -----------------------------------------


@pytest.mark.parametrize("urgency", ["urgent", "lapsed"])
def test_urgent_or_lapsed_queue_blocks_the_close(urgency):
    assert ims_severity({"urgency": urgency}) == "block"


@pytest.mark.parametrize("urgency", ["safe", "due_soon"])
def test_a_queue_with_runway_only_warns(urgency):
    assert ims_severity({"urgency": urgency}) == "warn"


def test_check_value_is_quiet_when_nothing_is_pending():
    assert ims_check_value(0, _rollup([])) == "0 pending"


def test_check_value_states_the_amount_and_the_deadline():
    value = ims_check_value(2, _rollup([Row(), Row()]))
    assert "2 pending" in value
    assert "in 19d" in value
    assert "2,000.00" in value, "₹2,000 of ITC across two rows"


def test_check_value_says_today_rather_than_in_0d():
    clock = _rollup([Row()], now=datetime(2026, 9, 20, tzinfo=UTC))
    assert "today" in ims_check_value(1, clock)


def test_check_value_reports_lapsed_credit_in_the_past_tense():
    clock = _rollup([Row()], now=datetime(2026, 9, 25, tzinfo=UTC))
    assert "already deemed accepted" in ims_check_value(1, clock)
