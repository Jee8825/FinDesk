"""Leak scoring — test vectors.

Two properties matter more than the arithmetic: the score must never rank a
commitment (rent, payroll) as a leak, and "recoverable" must stay conservative
— evidenced money only, unless a human has told us the thing is unused.
"""

from __future__ import annotations

from findesk_agents.graphs.subscription_scan.scoring import (
    portfolio_totals,
    rank,
    recommend,
    run_rate_paise,
    score_one,
)

MONTHLY = {
    "vendor_slug": "acme", "vendor_label": "Acme", "category_code": "software_cloud",
    "cadence": "monthly", "periods_per_year": 12, "status": "active",
    "latest_amount_paise": 100_000, "last_seen": "2026-07-05T00:00:00+00:00",
    "days_until_next": 25,
}
NO_DRIFT = {"kind": "stable", "step_change": None, "annualized_extra_paise": 0, "note": ""}
HIKE = {
    "kind": "price_increase",
    "step_change": {"pct": 0.15, "from_paise": 100_000, "to_paise": 115_000,
                    "effective_from": "2026-04-05T00:00:00+00:00"},
    "annualized_extra_paise": 15_000 * 12,
    "note": "Price moved +15.0% from 2026-04-05 and stayed there.",
}


def _c(**over):
    return {**MONTHLY, **over}


# --- run rate -------------------------------------------------------------


def test_run_rate_annualizes_by_cadence():
    assert run_rate_paise(_c()) == 100_000 * 12
    assert run_rate_paise(_c(cadence="annual", periods_per_year=1)) == 100_000


def test_irregular_cadence_has_no_run_rate():
    assert run_rate_paise(_c(periods_per_year=None)) == 0


# --- exclusions: the failure mode that would discredit the tool -----------


def test_payroll_is_never_a_leak():
    out = score_one(_c(category_code="payroll", latest_amount_paise=50_00_000), HIKE)
    assert out["leak_score"] == 0
    assert out["recoverable_paise_per_year"] == 0
    assert "not a discretionary subscription" in out["reason"]


def test_rent_is_never_a_leak_in_either_mode():
    for mode in ("business", "personal"):
        out = score_one(_c(category_code="rent"), HIKE, mode=mode)
        assert out["leak_score"] == 0, f"rent scored in {mode} mode"


def test_personal_mode_also_excludes_insurance_and_emi():
    for cat in ("insurance", "loan_emi"):
        assert score_one(_c(category_code=cat), HIKE, mode="personal")["leak_score"] == 0


def test_business_mode_does_not_exclude_insurance():
    """Business insurance is reviewable spend; personal cover is a commitment."""
    assert score_one(_c(category_code="insurance"), HIKE, mode="business")["leak_score"] > 0


def test_a_stopped_subscription_is_not_a_leak():
    out = score_one(_c(status="stopped"), HIKE)
    assert out["leak_score"] == 0
    assert out["recoverable_paise_per_year"] == 0
    assert "Already stopped" in out["reason"]


# --- recoverable stays conservative --------------------------------------


def test_a_clean_subscription_recovers_nothing():
    out = score_one(_c(), NO_DRIFT)
    assert out["recoverable_paise_per_year"] == 0
    assert out["leak_score"] == 0


def test_an_unapproved_hike_is_recoverable():
    out = score_one(_c(), HIKE)
    assert out["recoverable_paise_per_year"] == 15_000 * 12
    assert out["score_components"]["drift"] > 0


def test_suspicion_alone_never_makes_the_full_cost_recoverable():
    """Bank data cannot know whether anyone logged in. Never counted."""
    out = score_one(_c(), NO_DRIFT, category_peers=3, usage=None)
    assert out["recoverable_paise_per_year"] == 0
    assert out["leak_score"] > 0, "redundancy still raises the score"


def test_confirmed_unused_unlocks_the_whole_run_rate():
    """The confirmation loop is what licenses the big number."""
    out = score_one(_c(), NO_DRIFT, usage="unused")
    assert out["recoverable_paise_per_year"] == 100_000 * 12
    assert out["recommended_action"].startswith("Cancel")


def test_confirmed_in_use_does_not():
    out = score_one(_c(), NO_DRIFT, usage="in_use")
    assert out["recoverable_paise_per_year"] == 0


def test_duplicate_charges_are_recoverable():
    out = score_one(_c(), NO_DRIFT, duplicate_paise=100_000)
    assert out["recoverable_paise_per_year"] == 100_000
    assert out["score_components"]["duplicate"] == 25


# --- score behaviour ------------------------------------------------------


def test_components_are_always_exposed():
    out = score_one(_c(), HIKE, category_peers=2)
    assert set(out["score_components"]) == {
        "drift", "duplicate", "unused", "redundancy", "renewal"
    }
    assert out["leak_score"] <= 100


def test_bigger_spend_scores_higher_for_the_same_signal():
    small = score_one(_c(latest_amount_paise=5_000), HIKE)
    large = score_one(_c(latest_amount_paise=500_000), HIKE)
    assert large["leak_score"] > small["leak_score"]


def test_magnitude_scales_but_never_erases_a_clear_leak():
    tiny = score_one(_c(latest_amount_paise=1_000), HIKE, duplicate_paise=500)
    assert tiny["leak_score"] > 0, "a small but evidenced leak must still surface"


def test_annual_renewal_inside_the_horizon_scores():
    out = score_one(_c(cadence="annual", periods_per_year=1, days_until_next=20), NO_DRIFT)
    assert out["score_components"]["renewal"] == 15
    assert out["renewal_due"] is True


def test_a_distant_annual_renewal_does_not():
    out = score_one(_c(cadence="annual", periods_per_year=1, days_until_next=200), NO_DRIFT)
    assert out["score_components"]["renewal"] == 0


# --- recommendations ------------------------------------------------------


def test_seat_creep_recommends_headcount_reconciliation_not_a_dispute():
    action = recommend({"kind": "seat_creep"}, unused=False, renewal_due=False, peers=1)
    assert "headcount" in action
    assert "dispute" not in action.lower()


def test_confirmed_unused_beats_every_other_recommendation():
    action = recommend({"kind": "price_increase"}, unused=True, renewal_due=True, peers=3)
    assert action.startswith("Cancel")


def test_usage_based_is_not_told_to_cancel():
    action = recommend({"kind": "usage_based"}, unused=False, renewal_due=False, peers=1)
    assert "budget alert" in action


# --- ranking & totals -----------------------------------------------------


def test_ranking_puts_real_money_above_a_high_score_on_pennies():
    rows = [
        {"recoverable_paise_per_year": 60_000, "leak_score": 95, "run_rate_paise": 70_000},
        {"recoverable_paise_per_year": 800_000, "leak_score": 55, "run_rate_paise": 900_000},
    ]
    assert rank(rows)[0]["recoverable_paise_per_year"] == 800_000


def test_portfolio_totals_exclude_stopped_and_group_by_category():
    rows = [
        score_one(_c(), HIKE),
        score_one(_c(vendor_slug="b", category_code="marketing",
                     latest_amount_paise=200_000), NO_DRIFT),
        score_one(_c(vendor_slug="c", status="stopped"), NO_DRIFT),
    ]
    t = portfolio_totals(rows)
    assert t["subscriptions"] == 2
    assert t["stopped"] == 1
    assert t["committed_paise_per_year"] == 100_000 * 12 + 200_000 * 12
    assert t["recoverable_paise_per_year"] == 15_000 * 12
    assert t["leaking_count"] == 1
    assert list(t["by_category_paise"]) == ["marketing", "software_cloud"]
