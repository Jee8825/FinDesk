"""behavior_stats + spread-aware downside band — crucible I3 upgrade."""

from datetime import UTC, datetime

from findesk_agents.graphs.cash_forecast.engine import behavior_stats, project

START = datetime(2026, 7, 1, tzinfo=UTC)


def _invoice(due: str) -> dict:
    return {
        "id": "i1",
        "number": "INV-1",
        "client": "Acme",
        "client_id": "c1",
        "amount_paise": 10_000_000,
        "due_date": due,
    }


def test_median_resists_outliers():
    # one 60-day disaster must not drag the central estimate
    assert behavior_stats([5, 6, 7, 60])["median_late"] == 6.5
    assert behavior_stats([10])["median_late"] == 10.0
    assert behavior_stats([-3, 4])["median_late"] == 0.5


def test_spread_needs_four_observations():
    assert behavior_stats([5, 50])["spread_days"] == 0.0
    assert behavior_stats([2, 4, 30, 40])["spread_days"] > 0


def test_wide_spread_widens_only_the_downside_band():
    kwargs = dict(
        start=START,
        opening_balance_paise=0,
        open_invoices=[_invoice("2026-07-06T00:00:00+00:00")],
        avg_late_by_client={"c1": 0.0},
        monthly_outflows={},
    )
    flat = project(**kwargs)
    wide = project(**kwargs, spread_by_client={"c1": 35.0})

    def inflow_week(result: dict, scenario: str) -> int:
        return next(
            w["week"] for w in result["scenarios"][scenario] if w["inflow_paise"] > 0
        )

    # base and upside identical; downside pushed further out by the dispersion
    assert inflow_week(wide, "base") == inflow_week(flat, "base")
    assert inflow_week(wide, "upside") == inflow_week(flat, "upside")
    assert inflow_week(wide, "downside") > inflow_week(flat, "downside")


def test_small_spread_keeps_flat_slip_floor():
    kwargs = dict(
        start=START,
        opening_balance_paise=0,
        open_invoices=[_invoice("2026-07-06T00:00:00+00:00")],
        avg_late_by_client={"c1": 0.0},
        monthly_outflows={},
    )
    # spread below DOWNSIDE_SLIP_DAYS must not narrow the band below the floor
    flat = project(**kwargs)
    small = project(**kwargs, spread_by_client={"c1": 3.0})
    assert small["scenarios"]["downside"] == flat["scenarios"]["downside"]
