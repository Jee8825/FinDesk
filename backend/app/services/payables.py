"""Buyer-side MSME payables compliance — §15 clock + MSME disallowance exposure.

The disallowance section is NOT hardcoded. It was §43B(h) of the Income-tax
Act 1961 and is re-enacted as §37(2)(g) of the Income-tax Act 2025 (in force
1 Apr 2026), and both are live during the transition — FY 2025-26 is still
cited under §43B(h) via the §536 saving clause while it remains under audit.
Every citation therefore comes from statutory.msme_disallowance_citation(),
keyed to the bill's own tax year.

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
    msme_disallowance_citation,
    overdue_days,
    statutory_due,
)

# Counterparty.msme_status values that put a vendor inside §15/§16 and 43B(h).
# "medium" enterprises are outside 43B(h) (it covers micro & small only).
MSE_STATUSES = {"micro", "small", "registered_mse"}


def effective_mse(self_status: str, verified_category: str | None) -> tuple[bool, str, bool]:
    """(in_scope, source, drift) — the Udyam-verified category, when present,
    decides §15/43B(h) scope; the self-declared tag is only the fallback.

    Drift = the verified register disagrees with the self-declared tag about
    scope (e.g. a vendor tagged small verifies medium: it grew out of 43B(h)
    between FYs). Pure — unit-tested without a DB.
    """
    if not verified_category:
        return self_status in MSE_STATUSES, "self_declared", False
    in_scope = verified_category in {"micro", "small"}
    drift = (self_status in MSE_STATUSES) != in_scope
    return in_scope, "verified", drift

def ca_note(now: datetime) -> str:
    """Preparation-only framing, citing the section that governs `now`."""
    citation = msme_disallowance_citation(now)
    return (
        f"{citation['label']} exposure ({citation['act']}, tax year "
        f"{citation['tax_year']}) and §16 interest are computed as preparation "
        "only — confirm vendor Udyam status and figures with your CA before "
        "filing."
    )


# Kept for callers that only need the shape; prefer ca_note(now).
CA_NOTE = (
    "MSME disallowance exposure and §16 interest are computed as preparation "
    "only — confirm vendor Udyam status and figures with your CA before filing."
)


async def gather_items(session, tenant_id: str, now: datetime, *, bank_rate_bps: int):
    """MSE bills with computed clocks — shared by the routes and the export.

    Returns (items, rows, amounts, non_mse_count); items are plain dicts so
    callers shape their own response models.
    """
    from app.db.books_repo import BooksRepo

    repo = BooksRepo(session)
    parties = {c.id: c for c in await repo.counterparties(tenant_id)}
    bills = await repo.open_bills(tenant_id)

    items: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    amounts: list[int] = []
    drift_alerts: list[dict[str, Any]] = []
    drift_seen: set[str] = set()
    non_mse = 0
    for bill in bills:
        party = parties.get(bill.counterparty_id)
        status = (party.msme_status or "").lower() if party else ""
        verified = (party.msme_verified_category or None) if party else None
        in_scope, source, drift = effective_mse(status, verified)
        if drift and party and party.id not in drift_seen:
            drift_seen.add(party.id)
            drift_alerts.append(
                {
                    "vendor": party.name,
                    "self_declared": status or "untagged",
                    "verified": verified,
                    "effect": (
                        "now inside 43B(h) scope"
                        if in_scope
                        else "outside 43B(h) — verified beyond small"
                    ),
                }
            )
        if not in_scope:
            non_mse += 1  # outside §15/43B(h); counted so callers can say so
            continue
        row = compliance_row(
            amount_paise=bill.outstanding_paise,  # §16/43B(h) run on the unpaid portion
            acceptance_date=bill.acceptance_date or bill.issue_date,
            now=now,
            bank_rate_bps=bank_rate_bps,
        )
        rows.append(row)
        amounts.append(bill.outstanding_paise)
        items.append(
            {
                "bill_id": bill.id,
                "bill_number": bill.number,
                "counterparty_id": bill.counterparty_id,
                "vendor": party.name if party else "unknown",
                "msme_status": verified if source == "verified" else status,
                "msme_source": source,
                "verified_category": verified,
                "amount_paise": bill.amount_paise,
                "outstanding_paise": bill.outstanding_paise,
                "clock": row,
            }
        )
    # most urgent first: breached by overdue days, then closing windows
    items.sort(key=lambda i: (-i["clock"]["overdue_days"], i["clock"]["days_left"]))
    return items, rows, amounts, non_mse, drift_alerts


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
        # MSME disallowance: if still unpaid at FY end, the expense deduction
        # defers to the
        # payment year. Exposure is the full bill amount once the window is
        # breached; §16 interest is never deductible.
        "disallowance_risk_paise": amount_paise if days_over > 0 else 0,
        "fy_end": fy_end(now).isoformat(),
        # the section a CA should see next to this figure, for THIS tax year
        "statute": msme_disallowance_citation(now),
    }


def defense_plan(
    items: list[dict[str, Any]],  # {bill_number, vendor, outstanding_paise, clock}
    *,
    cash_available_paise: int | None,
) -> dict[str, Any]:
    """Ranked pay-first plan protecting the MSME expense deduction. Pure.

    Ordering logic (deterministic, defensible to a CA):
    1. **Closing-window bills first, tightest deadline first** — paying inside
       §15 avoids the deferral entirely and no §16 interest ever accrues. The
       cheapest consequence is the one that never happens.
    2. **Breached bills by daily interest bleed, biggest first** — their
       deduction survives if paid before FY-end, but §16 interest (never
       deductible) accrues every day; the bleed rate is the urgency.

    ``cash_available_paise`` (latest forecast opening balance) caps what is
    marked affordable now; the plan itself is advice — FinDesk moves no money.
    """
    closing = [i for i in items if i["clock"]["band"] == "closing"]
    breached = [i for i in items if i["clock"]["band"] == "breached"]
    closing.sort(key=lambda i: (i["clock"]["days_left"], -i["outstanding_paise"]))

    def daily_bleed(i: dict[str, Any]) -> int:
        return round(i["outstanding_paise"] * i["clock"]["annual_rate_bps"] / 10_000 / 365)

    breached.sort(key=lambda i: (-daily_bleed(i), i["clock"]["overdue_days"]))

    plan: list[dict[str, Any]] = []
    allocated = 0
    for item in closing + breached:
        c = item["clock"]
        if c["band"] == "closing":
            why = (
                f"pay within {c['days_left']} day(s) to stay inside §15 — "
                "no deferral, no interest, ever"
            )
            action_by = c["statutory_due_date"][:10]
            bleed = 0
        else:
            bleed = daily_bleed(item)
            why = (
                f"§16 interest bleeds ~₹{bleed / 100:,.0f}/day (never deductible); "
                f"paying before FY-end ({c['fy_end'][:10]}) keeps the deduction this year"
            )
            action_by = c["fy_end"][:10]
        allocated += item["outstanding_paise"]
        plan.append(
            {
                "bill_number": item["bill_number"],
                "vendor": item["vendor"],
                "outstanding_paise": item["outstanding_paise"],
                "band": c["band"],
                "action_by": action_by,
                "why": why,
                "daily_bleed_paise": bleed,
                "affordable_now": (
                    cash_available_paise is None or allocated <= cash_available_paise
                ),
            }
        )
    return {
        "items": plan,
        "totals": {
            "planned_paise": sum(p["outstanding_paise"] for p in plan),
            "deduction_protected_paise": sum(p["outstanding_paise"] for p in plan),
            "daily_bleed_paise": sum(p["daily_bleed_paise"] for p in plan),
        },
        "cash_basis_paise": cash_available_paise,
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
