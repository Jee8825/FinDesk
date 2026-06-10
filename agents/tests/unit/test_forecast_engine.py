"""B3 forecast engine tests — pure projection logic."""

from datetime import UTC, datetime

from findesk_agents.graphs.cash_forecast.engine import detect_gap, project

START = datetime(2026, 6, 15, tzinfo=UTC)


def _invoice(
    id="i1", number="INV-1", client="Acme", client_id="c1", amount=10_000_000, due="2026-06-20"
):
    return {
        "id": id,
        "number": number,
        "client": client,
        "client_id": client_id,
        "amount_paise": amount,
        "due_date": f"{due}T00:00:00+00:00",
    }


def test_inflow_lands_in_predicted_week_per_scenario():
    result = project(
        start=START,
        opening_balance_paise=0,
        open_invoices=[_invoice()],  # due 2026-06-20 (week 0)
        avg_late_by_client={"c1": 10.0},  # predicted 06-30 → week 2
        monthly_outflows={},
        horizon_weeks=8,
    )
    upside = result["scenarios"]["upside"]
    base = result["scenarios"]["base"]
    down = result["scenarios"]["downside"]
    assert upside[0]["inflow_paise"] == 10_000_000  # due date, week 0
    assert base[2]["inflow_paise"] == 10_000_000  # +10d late
    assert down[4]["inflow_paise"] == 10_000_000  # +10d +14d slip


def test_overdue_inflow_lands_in_week_zero():
    result = project(
        start=START,
        opening_balance_paise=0,
        open_invoices=[_invoice(due="2026-05-01")],
        avg_late_by_client={},
        monthly_outflows={},
        horizon_weeks=4,
    )
    assert result["scenarios"]["upside"][0]["inflow_paise"] == 10_000_000


def test_outflows_spread_and_balances_accumulate():
    result = project(
        start=START,
        opening_balance_paise=1_000_000,
        open_invoices=[],
        avg_late_by_client={},
        monthly_outflows={"rent": 4_330_000},  # → 1_000_000/week
        horizon_weeks=3,
    )
    closings = [w["closing_paise"] for w in result["scenarios"]["base"]]
    assert closings == [0, -1_000_000, -2_000_000]


def test_gap_detection_and_attribution():
    result = project(
        start=START,
        opening_balance_paise=2_000_000,
        open_invoices=[_invoice(amount=20_000_000, due="2026-07-20")],  # week 5
        avg_late_by_client={"c1": 20.0},
        monthly_outflows={"payroll": 8_660_000},  # 2_000_000/week
        horizon_weeks=13,
    )
    gap = result["gap"]
    assert gap is not None
    assert gap["scenario"] == "downside"
    assert gap["week"] == 1  # 2L opening - 2L/wk → negative in week 2 (index 1)
    assert gap["delayed_inflows"][0]["invoice_number"] == "INV-1"
    assert any("Largest lever" in line for line in result["narrative"])


def test_no_gap_when_funded():
    result = project(
        start=START,
        opening_balance_paise=100_000_000,
        open_invoices=[],
        avg_late_by_client={},
        monthly_outflows={"rent": 4_330_000},
        horizon_weeks=4,
    )
    assert result["gap"] is None
    assert detect_gap(result["scenarios"]) is None
