"""Unit tests for the scenario-sandbox math (pure, no datastores)."""

from __future__ import annotations

from app.services.whatif import apply_whatif, clamp_params


def _weeks(inflows: list[int], outflow: int = 10_000) -> list[dict]:
    weeks = []
    closing = 100_000
    for i, inflow in enumerate(inflows):
        closing = closing + inflow - outflow
        weeks.append(
            {
                "week": i + 1,
                "week_start": f"2026-08-{3 + i * 7:02d}",
                "inflow_paise": inflow,
                "outflow_paise": outflow,
                "closing_paise": closing,
            }
        )
    return weeks


def test_identity_when_params_zero():
    base = _weeks([50_000, 0, 20_000, 0])
    out = apply_whatif(base, 100_000, clamp_params({}))
    assert [w["closing_paise"] for w in out["weeks"]] == [w["closing_paise"] for w in base]
    assert out["gap"] is None
    assert out["end_delta_paise"] == 0
    assert out["pushed_out_paise"] == 0


def test_collection_delay_shifts_whole_weeks():
    base = _weeks([70_000, 0, 0, 0])
    out = apply_whatif(base, 100_000, clamp_params({"collection_delay_days": 14}))
    inflows = [w["inflow_paise"] for w in out["weeks"]]
    assert inflows == [0, 0, 70_000, 0]
    # end state identical — money arrived later but still inside horizon
    assert out["end_delta_paise"] == 0


def test_delay_past_horizon_drops_and_reports():
    base = _weeks([0, 0, 0, 40_000])
    out = apply_whatif(base, 100_000, clamp_params({"collection_delay_days": 21}))
    assert out["pushed_out_paise"] == 40_000
    assert out["end_delta_paise"] == -40_000


def test_haircut_trims_every_inflow_in_bps():
    base = _weeks([10_000, 10_000])
    out = apply_whatif(base, 100_000, clamp_params({"inflow_haircut_bps": 2500}))
    assert [w["inflow_paise"] for w in out["weeks"]] == [7_500, 7_500]


def test_extra_outflow_finds_the_gap_week():
    base = _weeks([0, 0, 0, 0], outflow=30_000)  # closings: 70k, 40k, 10k, -20k
    out = apply_whatif(base, 100_000, clamp_params({}))
    assert out["gap"] == {
        "scenario": "whatif",
        "week": 4,
        "week_start": base[3]["week_start"],
        "shortfall_paise": 20_000,
    }
    heavier = apply_whatif(
        base, 100_000, clamp_params({"extra_monthly_outflow_paise": 130_000})
    )
    assert heavier["gap"]["week"] < 4  # extra burn pulls the gap earlier


def test_params_clamped_against_abuse():
    p = clamp_params(
        {
            "collection_delay_days": 10_000,
            "inflow_haircut_bps": -5,
            "extra_monthly_outflow_paise": "nonsense",
        }
    )
    assert p["collection_delay_days"] == 60
    assert p["inflow_haircut_bps"] == 0
    assert p["extra_monthly_outflow_paise"] == 0


def test_empty_forecast_is_safe():
    out = apply_whatif([], 0, clamp_params({}))
    assert out == {"weeks": [], "gap": None, "pushed_out_paise": 0, "end_delta_paise": 0}
