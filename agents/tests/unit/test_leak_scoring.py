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
    out = score_one(_c(category_code="streaming"), NO_DRIFT, category_peers=3, usage=None)
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
    out = score_one(_c(category_code="streaming"), HIKE, category_peers=2)
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


# --- redundancy only counts where the category implies the same job ---------


def test_redundancy_fires_for_genuinely_overlapping_categories():
    out = score_one(_c(category_code="streaming"), NO_DRIFT, category_peers=3)
    assert out["score_components"]["redundancy"] == 15


def test_redundancy_is_suppressed_for_catch_all_software_cloud():
    """AWS and GitHub are both software_cloud and overlap not at all. Left
    unguarded this signal fires on every SaaS tool a company owns."""
    out = score_one(_c(category_code="software_cloud"), NO_DRIFT, category_peers=8)
    assert out["score_components"]["redundancy"] == 0
    assert out["leak_score"] == 0, "no other signal — must stay quiet"


def test_two_peers_scores_half_the_redundancy_weight():
    out = score_one(_c(category_code="cloud_storage"), NO_DRIFT, category_peers=2)
    assert out["score_components"]["redundancy"] == 7.5


def test_category_peer_counts_ignores_stopped_series():
    from findesk_agents.graphs.subscription_scan.scoring import category_peer_counts

    counts = category_peer_counts([
        {"category_code": "streaming", "status": "active"},
        {"category_code": "streaming", "status": "active"},
        {"category_code": "streaming", "status": "stopped"},
        {"category_code": "rent", "status": "active"},
    ])
    assert counts == {"streaming": 2, "rent": 1}


# --- the score must never contradict its own rupee figure -------------------

SEAT_CREEP = {
    "kind": "seat_creep",
    "step_change": None,
    "seat_creep": {"step_paise": 120_000, "steps": 3, "total_paise": 360_000},
    "annualized_extra_paise": 360_000 * 12,
    "note": "Rising in steps of about 1,200 rupees (3 increases) — this looks "
            "like seats added rather than a price change.",
}


def test_seat_creep_scores_even_though_it_has_no_step_change():
    """Regression: seat creep reports no step_change, so a pct-only drift
    component left the top recoverable row sitting at score 0."""
    out = score_one(_c(latest_amount_paise=720_000), SEAT_CREEP)
    assert out["recoverable_paise_per_year"] > 0
    assert out["leak_score"] > 0, "a row with recoverable money cannot score zero"
    assert out["score_components"]["drift"] > 0


def test_any_row_with_recoverable_money_scores_above_zero():
    """The invariant behind that regression, and it is ONE-directional.

    recoverable > 0 must imply score > 0 — money always has to rank. The
    converse is deliberately false: an annual renewal coming up, or three
    overlapping streaming services, are advisory signals worth surfacing with
    nothing yet recoverable. Asserting equivalence here would fail on perfectly
    correct data.
    """
    cases = [
        score_one(_c(), HIKE),
        score_one(_c(latest_amount_paise=720_000), SEAT_CREEP),
        score_one(_c(), NO_DRIFT, duplicate_paise=50_000),
        score_one(_c(), NO_DRIFT, usage="unused"),
    ]
    for out in cases:
        assert out["recoverable_paise_per_year"] > 0
        assert out["leak_score"] > 0, out


def test_advisory_signals_score_without_any_recoverable_money():
    """The converse direction, stated so nobody 'fixes' it into equivalence."""
    renewal = score_one(
        _c(cadence="annual", periods_per_year=1, days_until_next=20), NO_DRIFT
    )
    redundant = score_one(_c(category_code="streaming"), NO_DRIFT, category_peers=3)
    for out in (renewal, redundant):
        assert out["leak_score"] > 0
        assert out["recoverable_paise_per_year"] == 0


def test_a_duplicate_charge_is_recommended_even_when_the_price_is_stable():
    """Regression: a row with a recoverable duplicate said "Keep — no leak signal
    detected", which reads as a bug sitting next to a rupee figure."""
    out = score_one(_c(), NO_DRIFT, duplicate_paise=236_000)
    assert out["recoverable_paise_per_year"] == 236_000
    assert "duplicate" in out["recommended_action"].lower()
    assert "no leak signal" not in out["recommended_action"]


def test_consolidation_advice_only_fires_for_allowlisted_categories():
    """Redundancy advice must follow the same allowlist as the score, or the
    text and the number disagree."""
    catch_all = score_one(_c(category_code="software_cloud"), NO_DRIFT, category_peers=8)
    assert "Consolidate" not in catch_all["recommended_action"]
    real = score_one(_c(category_code="streaming"), NO_DRIFT, category_peers=3)
    assert "Consolidate" in real["recommended_action"]
