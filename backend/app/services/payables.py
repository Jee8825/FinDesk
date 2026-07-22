"""Buyer-side MSME payables compliance — §15 clock + 43B(h) tax exposure.

The same statutory engine that powers the receivables radar, pointed the other
way: bills *we* owe vendors who are registered micro/small enterprises.

Why this exists (crucible finding I1): suppliers are often afraid to enforce
the 45-day clock against customers, but buyers have a hard *legal* incentive to
comply — Income-tax Act §43B(h) defers the expense deduction on any MSE bill
unpaid past the §15 deadline to the year of actual payment. Interest owed under
§16 is additionally not deductible at all. This module computes both exposures
deterministically; NO LLM TOUCHES THIS MODULE.

Framing rule: outputs are preparation for the tenant and their CA — FinDesk
never files anything and never moves money.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.statutory import (
    DEFAULT_BANK_RATE_BPS,
    STATUTORY_WINDOW_DAYS,
    accrued_interest_paise,
    annual_rate_bps,
    overdue_days,
    statutory_due,
)

# Counterparty.msme_status values that put a vendor inside §15/§16 and 43B(h).
# "medium" enterprises are outside 43B(h) (it covers micro & small only).
MSE_STATUSES = {"micro", "small", "registered_mse"}

CA_NOTE = (
    "43B(h) exposure and §16 interest are computed as preparation only — "
    "confirm vendor Udyam status and figures with your CA before filing."
)


def fy_end(now: datetime) -> datetime:
    """The Indian financial-year end (31 March, IST) this instant falls in.

    Computed on the IST calendar — a bill assessed on 31 Mar IST evening is
    already in the next FY by UTC clock, so the UTC date alone would misplace
    the boundary by a day.
    """
    from zoneinfo import ZoneInfo

    ist_now = now.astimezone(ZoneInfo("Asia/Kolkata"))
    year = ist_now.year if (ist_now.month, ist_now.day) <= (3, 31) else ist_now.year + 1
    # 31 Mar 23:59:59 IST expressed back in UTC
    return datetime(year, 3, 31, 23, 59, 59, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(UTC)


def compliance_row(
    *,
    amount_paise: int,
    acceptance_date: datetime,
    now: datetime,
    bank_rate_bps: int = DEFAULT_BANK_RATE_BPS,
) -> dict[str, Any]:
    """One open MSE bill's full buyer-side statutory state. Pure."""
    due = statutory_due(acceptance_date)
    days_over = overdue_days(acceptance_date, now)
    days_left = max(0, (due - now).days)
    interest = accrued_interest_paise(amount_paise, days_over, bank_rate_bps)
    if days_over > 0:
        band = "breached"
    elif days_left <= 7:
        band = "closing"  # inside the last week of the window
    else:
        band = "within"
    return {
        "acceptance_date": acceptance_date.isoformat(),
        "statutory_due_date": due.isoformat(),
        "day_count": max(0, min((now - acceptance_date).days, STATUTORY_WINDOW_DAYS)),
        "days_left": days_left,
        "overdue_days": days_over,
        "band": band,
        # §16: interest we owe the vendor (compound, monthly rests, 3× bank rate)
        "interest_owed_paise": interest,
        "annual_rate_bps": annual_rate_bps(bank_rate_bps),
        # 43B(h): if still unpaid at FY end, the expense deduction defers to the
        # payment year. Exposure is the full bill amount once the window is
        # breached; §16 interest is never deductible.
        "disallowance_risk_paise": amount_paise if days_over > 0 else 0,
        "fy_end": fy_end(now).isoformat(),
    }


def totals(rows: list[dict[str, Any]], amounts: list[int]) -> dict[str, int]:
    """Roll-up for the header cards. rows[i] corresponds to amounts[i]."""
    return {
        "open_mse_paise": sum(amounts),
        "breached_paise": sum(
            a for r, a in zip(rows, amounts, strict=True) if r["band"] == "breached"
        ),
        "closing_window_paise": sum(
            a for r, a in zip(rows, amounts, strict=True) if r["band"] == "closing"
        ),
        "interest_owed_paise": sum(r["interest_owed_paise"] for r in rows),
        "disallowance_risk_paise": sum(r["disallowance_risk_paise"] for r in rows),
    }
