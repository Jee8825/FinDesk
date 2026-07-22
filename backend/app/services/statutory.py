"""MSME Act 45-day statutory clock engine — pure, deterministic, test-vectored.

Legal basis (framing only — FinDesk prepares computations, never files):

* **Section 15**: the buyer must pay by the agreed date, which cannot exceed
  45 days from the day of acceptance of goods/services.
* **Section 16**: on default, compound interest **with monthly rests** at
  three times the bank rate notified by RBI.

Implementation choices (documented because the statute leaves rounding open):
* Acceptance date defaults to the invoice issue date when not recorded.
* Full overdue months compound monthly; the trailing partial month accrues
  simple interest pro-rata on the compounded balance (a common, conservative
  convention — CAs may recompute; every figure ships with 'review with your
  CA' framing).
* All arithmetic in integer paise with float intermediates rounded half-up at
  the end of each step, so results are reproducible to the paisa.

NO LLM TOUCHES THIS MODULE. Escalation wording is chosen elsewhere; the
ladder *states* below are fixed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

STATUTORY_WINDOW_DAYS = 45
BANK_RATE_MULTIPLIER = 3
# RBI bank rate 6.75% (last verified Jul 2026). §16 interest = 3× this figure,
# so a stale value silently mis-states statutory interest — whoever operates a
# deployment owns re-verifying it against rbi.org.in after every MPC revision
# and overriding via the bank_rate_bps parameter/config, not by editing here.
DEFAULT_BANK_RATE_BPS = 675

# escalation ladder: states are deterministic; agents choose words, not steps
LADDER = (
    (0, "none"),
    (1, "nudge"),
    (16, "reminder"),
    (31, "act_letter"),
    (61, "samadhaan_prep"),
)


def statutory_due(acceptance_date: datetime) -> datetime:
    return acceptance_date + timedelta(days=STATUTORY_WINDOW_DAYS)


def overdue_days(acceptance_date: datetime, now: datetime) -> int:
    return max(0, (now - statutory_due(acceptance_date)).days)


def escalation_level(days: int) -> str:
    level = "none"
    for threshold, name in LADDER:
        if days >= threshold:
            level = name
    return level


def annual_rate_bps(bank_rate_bps: int = DEFAULT_BANK_RATE_BPS) -> int:
    return bank_rate_bps * BANK_RATE_MULTIPLIER


def accrued_interest_paise(
    principal_paise: int,
    days: int,
    bank_rate_bps: int = DEFAULT_BANK_RATE_BPS,
) -> int:
    """Compound interest with monthly rests for ``days`` overdue.

    Full 30-day months compound; the remainder accrues simple interest on the
    compounded balance. Returns interest only (excludes principal).
    """
    if days <= 0 or principal_paise <= 0:
        return 0
    monthly_rate = (
        Decimal(annual_rate_bps(bank_rate_bps)) / Decimal(10_000) / Decimal(12)
    )
    full_months, rem_days = divmod(days, 30)
    balance = Decimal(principal_paise)
    for _ in range(full_months):
        balance = (balance * (1 + monthly_rate)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    if rem_days:
        balance = (balance * (1 + monthly_rate * Decimal(rem_days) / Decimal(30))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    return int(balance) - principal_paise


def clock_snapshot(
    *,
    acceptance_date: datetime,
    amount_paise: int,
    now: datetime,
    bank_rate_bps: int = DEFAULT_BANK_RATE_BPS,
) -> dict:
    """One invoice's full statutory state — the radar's row payload."""
    due = statutory_due(acceptance_date)
    days = overdue_days(acceptance_date, now)
    return {
        "acceptance_date": acceptance_date.isoformat(),
        "statutory_due_date": due.isoformat(),
        # days consumed on the 45-day clock, clamped to [0, 45]
        "day_count": max(0, min((now - acceptance_date).days, STATUTORY_WINDOW_DAYS)),
        "overdue_days": days,
        "accrued_interest_paise": accrued_interest_paise(amount_paise, days, bank_rate_bps),
        "annual_rate_bps": annual_rate_bps(bank_rate_bps),
        "escalation_level": escalation_level(days),
    }
