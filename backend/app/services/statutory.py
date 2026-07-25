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

from datetime import UTC, datetime, timedelta
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


# --------------------------------------------------------------------------
# GST Invoice Management System — the deemed-acceptance clock
# --------------------------------------------------------------------------
# Second statutory clock, same posture as §15 above: pure, deterministic, and
# it never decides — it states a date and a consequence.
#
# Legal basis (framing only — FinDesk prepares, never files):
#
# * A supplier-filed record sitting in IMS may be kept **pending for one tax
#   period**: one month for a monthly filer, one quarter under QRMP.
# * If no accept/reject action is taken by that deadline, the portal marks the
#   record **deemed accepted**. Silence is not neutral — it *is* a decision,
#   made for you, and it fixes your ITC position for the period.
# * From the July-2026 period, Table 4 of GSTR-3B is hard-locked: ITC is
#   auto-populated from GSTR-2B/IMS and no longer manually editable, so a
#   deemed acceptance can no longer be corrected on your own return.
#
# Implementation choices (documented because the rules leave edges open):
# * The deadline is the GSTR-3B due date of the tax period FOLLOWING the
#   record's own period — that is what "pending for one tax period" resolves to.
# * QRMP GSTR-3B due dates are staggered 22nd/24th by state group. We use the
#   22nd: being a day early costs nothing, being a day late costs the credit.
#   Deployments in a 24th-group state may override via GSTR3B_QUARTERLY_DUE_DAY.
# * Dates are date-granular in UTC. Portal cut-offs are IST wall-clock; the
#   day-level answer is what a human acts on, and the UI renders IST.
#
# NO LLM TOUCHES THIS MODULE.

GSTR3B_MONTHLY_DUE_DAY = 20
GSTR3B_QUARTERLY_DUE_DAY = 22
IMS_URGENT_DAYS = 7
IMS_DUE_SOON_DAYS = 30
FILING_FREQUENCIES = ("monthly", "quarterly")


def _add_months(year: int, month: int, months: int) -> tuple[int, int]:
    """Advance a (year, month) pair, 1-indexed months."""
    idx = (year * 12 + (month - 1)) + months
    return divmod(idx, 12)[0], divmod(idx, 12)[1] + 1


def parse_period(period: str) -> tuple[int, int]:
    """'2026-07' -> (2026, 7). Raises ValueError on anything else."""
    year_s, _, month_s = period.partition("-")
    year, month = int(year_s), int(month_s)
    if not 1 <= month <= 12:
        raise ValueError(f"month out of range in period {period!r}")
    return year, month


def quarter_end_month(month: int) -> int:
    """Last month of the GST quarter containing ``month`` (Apr-Jun, Jul-Sep, ...).

    GST quarters under QRMP follow the financial year: Apr-Jun, Jul-Sep,
    Oct-Dec, Jan-Mar.
    """
    return ((month - 1) // 3) * 3 + 3


def gstr3b_due(period: str, *, frequency: str = "monthly") -> datetime:
    """When GSTR-3B for ``period`` falls due.

    Monthly: the 20th of the following month. Quarterly: the 22nd of the month
    following the quarter that contains ``period``.
    """
    if frequency not in FILING_FREQUENCIES:
        raise ValueError(f"unknown filing frequency {frequency!r}")
    year, month = parse_period(period)
    if frequency == "monthly":
        y, m = _add_months(year, month, 1)
        return datetime(y, m, GSTR3B_MONTHLY_DUE_DAY, tzinfo=UTC)
    y, m = _add_months(year, quarter_end_month(month), 1)
    return datetime(y, m, GSTR3B_QUARTERLY_DUE_DAY, tzinfo=UTC)


def ims_deemed_accept_at(period: str, *, frequency: str = "monthly") -> datetime:
    """The moment an un-actioned record from ``period`` is deemed accepted.

    One tax period of grace, so the deadline is the GSTR-3B due date of the
    period *after* the record's own.
    """
    year, month = parse_period(period)
    step = 1 if frequency == "monthly" else 3
    y, m = _add_months(year, month, step)
    return gstr3b_due(f"{y:04d}-{m:02d}", frequency=frequency)


def ims_urgency(days_remaining: int) -> str:
    """Deterministic band. Words are chosen elsewhere; the bands are fixed."""
    if days_remaining < 0:
        return "lapsed"
    if days_remaining <= IMS_URGENT_DAYS:
        return "urgent"
    if days_remaining <= IMS_DUE_SOON_DAYS:
        return "due_soon"
    return "safe"


def ims_clock_snapshot(
    *,
    period: str,
    now: datetime,
    frequency: str = "monthly",
    tax_paise: int = 0,
) -> dict:
    """One pending record's deemed-acceptance state — the IMS row payload."""
    deadline = ims_deemed_accept_at(period, frequency=frequency)
    days_remaining = (deadline.date() - now.date()).days
    return {
        "period": period,
        "filing_frequency": frequency,
        "deemed_accept_at": deadline.isoformat(),
        "days_remaining": days_remaining,
        "urgency": ims_urgency(days_remaining),
        # what silence costs: the credit that gets accepted without a decision
        "itc_at_risk_paise": tax_paise if days_remaining >= 0 else 0,
        "itc_deemed_paise": tax_paise if days_remaining < 0 else 0,
    }


# --------------------------------------------------------------------------
# Which statute governs an MSME payment disallowance, and when
# --------------------------------------------------------------------------
# The Income-tax Act 2025 is in force from 1 April 2026. The MSME
# actual-payment disallowance that was **section 43B(h)** of the 1961 Act is
# re-enacted as **section 37(2)(g)** of the 2025 Act. The substance is unchanged
# — payment beyond the MSMED Act §15 window defers the deduction to the year of
# payment — but the citation is not, and a citation is the whole point of
# showing a section number to a CA.
#
# This is NOT a rename. Section 536 of the 2025 Act preserves the earlier Act
# for pre-cutover years, so BOTH are live right now:
#
#   * FY 2025-26 (year ended 31 Mar 2026) → 1961 Act, §43B(h). This is the year
#     under audit until the 30 September 2026 tax-audit deadline, and the MSME
#     disallowance is the line item most likely to move the tax number.
#   * Tax Year 2026-27 onward (from 1 Apr 2026) → 2025 Act, §37(2)(g).
#
# So the correct behaviour is to cite by the year the bill belongs to. Citing
# one section for everything is wrong in one direction or the other.
#
# NO LLM TOUCHES THIS MODULE.

ITA_2025_EFFECTIVE_FROM = datetime(2026, 4, 1, tzinfo=UTC)
# Indian financial year starts 1 April.
FY_START_MONTH = 4


def tax_year_of(as_of: datetime) -> str:
    """Indian tax year label for a date: '2026-27'."""
    start = as_of.year if as_of.month >= FY_START_MONTH else as_of.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def msme_disallowance_citation(as_of: datetime) -> dict[str, str]:
    """The statute to cite for an MSE bill falling in ``as_of``'s tax year.

    Returns both the governing citation and the other one, because during the
    transition a CA is working two years at once and a bare section number with
    no act attached is ambiguous.
    """
    if as_of >= ITA_2025_EFFECTIVE_FROM:
        return {
            "section": "37(2)(g)",
            "label": "§37(2)(g)",
            "act": "Income-tax Act 2025",
            "tax_year": tax_year_of(as_of),
            "predecessor": "§43B(h) (Income-tax Act 1961)",
            "note": (
                "The Income-tax Act 2025 applies from 1 Apr 2026; the MSME "
                "disallowance formerly at §43B(h) is re-enacted at §37(2)(g). "
                "FY 2025-26 is still cited under §43B(h)."
            ),
        }
    return {
        "section": "43B(h)",
        "label": "§43B(h)",
        "act": "Income-tax Act 1961",
        "tax_year": tax_year_of(as_of),
        "predecessor": "",
        "note": (
            "FY 2025-26 and earlier remain under the Income-tax Act 1961 "
            "(§536 saving clause); §37(2)(g) of the 2025 Act applies from "
            "1 Apr 2026."
        ),
    }
