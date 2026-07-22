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


def test_settings_default_rate_matches_engine_default():
    # config override exists so deployments can track RBI revisions; the two
    # defaults must not silently drift apart
    from app.config import Settings
    from app.services.statutory import DEFAULT_BANK_RATE_BPS

    assert Settings().statutory_bank_rate_bps == DEFAULT_BANK_RATE_BPS


def _plan_item(number, band, *, days_left=0, overdue=0, outstanding=1_000_000):
    from app.services.payables import compliance_row as _cr  # noqa: F401 — shape doc only

    return {
        "bill_number": number,
        "vendor": "V",
        "outstanding_paise": outstanding,
        "clock": {
            "band": band,
            "days_left": days_left,
            "overdue_days": overdue,
            "annual_rate_bps": 2025,
            "statutory_due_date": "2026-07-25T00:00:00+00:00",
            "fy_end": "2027-03-31T18:29:59+00:00",
        },
    }


def test_defense_plan_orders_closing_by_deadline_then_breached_by_bleed():
    from app.services.payables import defense_plan

    plan = defense_plan(
        [
            _plan_item("B-slow-bleed", "breached", overdue=40, outstanding=1_000_000),
            _plan_item("C-tight", "closing", days_left=1),
            _plan_item("B-big-bleed", "breached", overdue=5, outstanding=50_000_000),
            _plan_item("C-loose", "closing", days_left=6),
        ],
        cash_available_paise=None,
    )
    assert [p["bill_number"] for p in plan["items"]] == [
        "C-tight", "C-loose", "B-big-bleed", "B-slow-bleed",
    ]
    # closing rows never bleed; breached rows bleed daily at 3× bank rate / 365
    assert plan["items"][0]["daily_bleed_paise"] == 0
    assert plan["items"][2]["daily_bleed_paise"] == round(50_000_000 * 0.2025 / 365)
    assert plan["totals"]["planned_paise"] == 53_000_000


def test_defense_plan_cash_cap_marks_affordability_in_rank_order():
    from app.services.payables import defense_plan

    plan = defense_plan(
        [
            _plan_item("C1", "closing", days_left=2, outstanding=3_000_000),
            _plan_item("C2", "closing", days_left=4, outstanding=3_000_000),
        ],
        cash_available_paise=4_000_000,
    )
    assert [p["affordable_now"] for p in plan["items"]] == [True, False]
    assert plan["cash_basis_paise"] == 4_000_000
