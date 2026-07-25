"""Forecast critic — a correct projection passes; every broken shape is named."""

from datetime import UTC, datetime

from findesk_agents.graphs.cash_forecast.critic import review
from findesk_agents.graphs.cash_forecast.engine import project

START = datetime(2026, 7, 1, tzinfo=UTC)


def _real_projection() -> dict:
    return project(
        start=START,
        opening_balance_paise=10_000_000,
        open_invoices=[
            {
                "id": "i1", "number": "INV-1", "client": "Acme", "client_id": "c1",
                "amount_paise": 5_000_000, "due_date": "2026-07-10T00:00:00+00:00",
            }
        ],
        avg_late_by_client={"c1": 5.0},
        monthly_outflows={"AWS": 4_330_000},
        open_bills=[
            {"number": "PB-1", "vendor": "Vega", "outstanding_paise": 2_000_000,
             "due_date": "2026-07-20T00:00:00+00:00"},
        ],
    )


def test_real_engine_output_passes_clean():
    assert review(_real_projection()) == []


def test_continuity_break_is_caught_at_the_break():
    result = _real_projection()
    result["scenarios"]["base"][4]["closing_paise"] += 1  # tamper one week
    problems = review(result)
    # a mid-chain point edit breaks two adjacent links (the edit and its wake)
    assert 1 <= len(problems) <= 2
    assert "base w4" in problems[0] and "continuity" in problems[0]


def test_missing_scenario_and_wrong_length_are_named():
    result = _real_projection()
    del result["scenarios"]["downside"]
    result["scenarios"]["base"] = result["scenarios"]["base"][:5]
    problems = review(result)
    assert any("downside: scenario missing" in p for p in problems)
    assert any("base: 5 weeks, expected 13" in p for p in problems)


def test_negative_flow_and_bogus_gap_are_caught():
    result = _real_projection()
    result["scenarios"]["upside"][0]["inflow_paise"] = -5
    result["gap"] = {"scenario": "base", "week": 0}  # week 0 is positive here
    problems = review(result)
    assert any("negative flow" in p for p in problems)
    assert any("gap points at a week" in p for p in problems)


def test_inflow_total_inversion_is_caught():
    result = _real_projection()
    # base suddenly counts more inflow than upside — impossible by construction
    result["scenarios"]["base"][0]["inflow_paise"] += 1_000_000
    # keep continuity consistent so only the inversion fires
    running = result["opening_balance_paise"]
    for w in result["scenarios"]["base"]:
        running += w["inflow_paise"] - w["outflow_paise"]
        w["closing_paise"] = running
    problems = review(result)
    assert problems == [
        p for p in problems if "inflow totals inverted" in p
    ] and problems  # only the inversion, and at least it
