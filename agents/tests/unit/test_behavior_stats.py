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


def _bill(number: str, vendor: str, outstanding: int, due: str) -> dict:
    return {"number": number, "vendor": vendor, "outstanding_paise": outstanding, "due_date": due}


def test_dated_bill_lands_in_due_week_every_scenario():
    result = project(
        start=START,
        opening_balance_paise=100_000_000,
        open_invoices=[],
        avg_late_by_client={},
        monthly_outflows={},
        open_bills=[_bill("PB-1", "Vega Logistics", 5_000_000, "2026-07-16T00:00:00+00:00")],
    )
    for scenario in ("upside", "base", "downside"):
        weeks = result["scenarios"][scenario]
        assert weeks[2]["outflow_paise"] == 5_000_000  # due in week 2, all scenarios
        assert sum(w["outflow_paise"] for w in weeks) == 5_000_000
    assert any("dated vendor bill" in line for line in result["narrative"])


def test_dated_bill_replaces_vendor_baseline_not_others():
    result = project(
        start=START,
        opening_balance_paise=0,
        open_invoices=[],
        avg_late_by_client={},
        monthly_outflows={"VEGA LOGISTICS PVT": 4_330_000, "AWS India": 8_660_000},
        open_bills=[_bill("PB-1", "Vega Logistics", 5_000_000, "2026-07-16T00:00:00+00:00")],
    )
    # Vega's smoothed baseline (₹43.3k/mo → ₹10k/wk) is superseded by its
    # dated bill; AWS keeps recurring (₹86.6k/mo → ₹20k/wk)
    assert result["weekly_outflow_paise"] == 2_000_000
    assert [b["vendor"] for b in result["outflow_basis"]] == ["AWS India"]
    weeks = result["scenarios"]["base"]
    assert weeks[2]["outflow_paise"] == 2_000_000 + 5_000_000


def test_bill_beyond_horizon_is_ignored_and_overdue_lands_week_zero():
    result = project(
        start=START,
        opening_balance_paise=0,
        open_invoices=[],
        avg_late_by_client={},
        monthly_outflows={},
        open_bills=[
            _bill("PB-far", "X", 1_000_000, "2027-07-01T00:00:00+00:00"),
            _bill("PB-late", "Y", 2_000_000, "2026-06-01T00:00:00+00:00"),
        ],
    )
    weeks = result["scenarios"]["base"]
    assert weeks[0]["outflow_paise"] == 2_000_000  # already-due money is this week's problem
    assert sum(w["outflow_paise"] for w in weeks) == 2_000_000  # beyond-horizon ignored
