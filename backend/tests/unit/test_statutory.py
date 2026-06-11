"""Statutory engine test vectors — the legal moat must be exact to the paisa."""

from datetime import UTC, datetime

from app.services.statutory import (
    accrued_interest_paise,
    clock_snapshot,
    escalation_level,
    overdue_days,
    statutory_due,
)

ACCEPT = datetime(2026, 3, 1, tzinfo=UTC)


def test_statutory_due_is_45_days_from_acceptance():
    assert statutory_due(ACCEPT) == datetime(2026, 4, 15, tzinfo=UTC)


def test_overdue_days_clamps_at_zero():
    assert overdue_days(ACCEPT, datetime(2026, 4, 10, tzinfo=UTC)) == 0
    assert overdue_days(ACCEPT, datetime(2026, 4, 15, tzinfo=UTC)) == 0
    assert overdue_days(ACCEPT, datetime(2026, 4, 25, tzinfo=UTC)) == 10


def test_escalation_ladder_states():
    assert escalation_level(0) == "none"
    assert escalation_level(1) == "nudge"
    assert escalation_level(15) == "nudge"
    assert escalation_level(16) == "reminder"
    assert escalation_level(30) == "reminder"
    assert escalation_level(31) == "act_letter"
    assert escalation_level(60) == "act_letter"
    assert escalation_level(61) == "samadhaan_prep"


# Hand-computed vectors: ₹1,00,000 principal, bank rate 6.75% → 20.25%/yr,
# monthly rate = 0.0225/1.3333… = 0.016875.
def test_interest_zero_when_not_overdue():
    assert accrued_interest_paise(10_000_000, 0) == 0
    assert accrued_interest_paise(0, 100) == 0


def test_interest_one_full_month():
    # 10_000_000 × 0.016875 = 168,750 paise exactly
    assert accrued_interest_paise(10_000_000, 30) == 168_750


def test_interest_two_months_compounds():
    # m1: 10_168_750; m2: 10_168_750 × 1.016875 = 10_340_348 (rounded half-up)
    # interest = 340_348 — strictly more than 2× simple (337_500)
    assert accrued_interest_paise(10_000_000, 60) == 340_348


def test_interest_partial_month_pro_rata():
    # 15 days: 10_000_000 × 0.016875 × 15/30 = 84,375 simple
    assert accrued_interest_paise(10_000_000, 15) == 84_375
    # 45 days: one rest then half-month simple on compounded balance:
    # 10_168_750 × (1 + 0.016875 × 0.5) = 10_254_549 (rounded) → 254_549
    assert accrued_interest_paise(10_000_000, 45) == 254_549


def test_clock_snapshot_shape():
    snap = clock_snapshot(
        acceptance_date=ACCEPT,
        amount_paise=10_000_000,
        now=datetime(2026, 5, 15, tzinfo=UTC),  # 30 days overdue
    )
    assert snap["overdue_days"] == 30
    assert snap["accrued_interest_paise"] == 168_750
    assert snap["escalation_level"] == "reminder"
    assert snap["annual_rate_bps"] == 2025
    assert snap["statutory_due_date"].startswith("2026-04-15")


def test_day_count_clamps_to_window():
    early = clock_snapshot(
        acceptance_date=ACCEPT,
        amount_paise=10_000_000,
        now=datetime(2026, 3, 11, tzinfo=UTC),  # 10 days in
    )
    assert early["day_count"] == 10
    late = clock_snapshot(
        acceptance_date=ACCEPT,
        amount_paise=10_000_000,
        now=datetime(2026, 6, 1, tzinfo=UTC),  # way past the window
    )
    assert late["day_count"] == 45
    future = clock_snapshot(
        acceptance_date=ACCEPT,
        amount_paise=10_000_000,
        now=datetime(2026, 2, 25, tzinfo=UTC),  # acceptance recorded ahead
    )
    assert future["day_count"] == 0
