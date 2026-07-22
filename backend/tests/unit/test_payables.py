"""Buyer-side payables math — §15 bands, §16 interest owed, 43B(h) exposure, FY end."""

from datetime import UTC, datetime

from app.services.payables import MSE_STATUSES, compliance_row, fy_end, totals
from app.services.statutory import accrued_interest_paise

ISSUE = datetime(2026, 5, 20, tzinfo=UTC)


def _row(now: str, amount: int = 5_230_000) -> dict:
    return compliance_row(
        amount_paise=amount,
        acceptance_date=ISSUE,
        now=datetime.fromisoformat(now).replace(tzinfo=UTC),
    )


def test_within_window_carries_no_exposure():
    row = _row("2026-06-01")
    assert row["band"] == "within"
    assert row["days_left"] == 33
    assert row["interest_owed_paise"] == 0
    assert row["disallowance_risk_paise"] == 0


def test_closing_band_inside_final_week():
    row = _row("2026-06-30")  # due 2026-07-04 → 4 days left
    assert row["band"] == "closing"
    assert row["days_left"] == 4
    assert row["disallowance_risk_paise"] == 0  # not yet breached


def test_breach_accrues_16_interest_and_full_43bh_exposure():
    row = _row("2026-07-22")  # 18 days past the 45-day deadline
    assert row["band"] == "breached"
    assert row["overdue_days"] == 18
    # §16 figure must equal the shared engine's — same math both directions
    assert row["interest_owed_paise"] == accrued_interest_paise(5_230_000, 18)
    assert row["interest_owed_paise"] > 0
    assert row["disallowance_risk_paise"] == 5_230_000


def test_day_count_clamps_to_window():
    assert _row("2026-05-21")["day_count"] == 1
    assert _row("2026-09-01")["day_count"] == 45


def test_fy_end_is_march_31_ist_calendar():
    assert fy_end(datetime(2026, 7, 22, tzinfo=UTC)).astimezone(UTC).year == 2027
    # 31 Mar 20:00 UTC is already 1 Apr in IST → belongs to the NEXT FY
    late_utc = fy_end(datetime(2026, 3, 31, 20, 0, tzinfo=UTC))
    assert late_utc.year == 2027
    # 31 Mar 10:00 UTC is still 31 Mar IST → current FY
    same_day = fy_end(datetime(2026, 3, 31, 10, 0, tzinfo=UTC))
    assert same_day.year == 2026


def test_totals_bucket_by_band():
    rows = [_row("2026-07-22"), _row("2026-06-30", 2_000_000), _row("2026-06-01", 1_000_000)]
    t = totals(rows, [5_230_000, 2_000_000, 1_000_000])
    assert t["open_mse_paise"] == 8_230_000
    assert t["breached_paise"] == 5_230_000
    assert t["closing_window_paise"] == 2_000_000
    assert t["disallowance_risk_paise"] == 5_230_000
    assert t["interest_owed_paise"] == rows[0]["interest_owed_paise"]


def test_medium_enterprises_are_outside_43bh():
    assert "medium" not in MSE_STATUSES
    assert {"micro", "small"} <= MSE_STATUSES
