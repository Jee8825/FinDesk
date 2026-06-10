"""B3 forecast engine — pure weekly cash projection with scenario bands.

Inputs are facts and beliefs, never guesses:
* **Inflows**: each open invoice lands in the week of its *predicted* payment
  date — due date shifted by the client's remembered average lateness (B1).
* **Outflows**: vendors with a stable spend baseline (same maths as the
  anomaly scan) recur monthly, spread evenly across weeks; everything else is
  assumed already paid.
* **Scenarios**: base = predicted timing; upside = clients pay by due date;
  downside = predicted + DOWNSIDE_SLIP_DAYS. The band between upside and
  downside is the honest envelope — the spec demands bands, not point lies.

A *gap* is the first week where any scenario's closing balance goes below
zero; attribution names the delayed inflows that would have prevented it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from findesk_shared import format_inr

DEFAULT_HORIZON_WEEKS = 13
DOWNSIDE_SLIP_DAYS = 14
DEFAULT_PAY_DELAY_DAYS = 7  # clients with no history: assume a week late
WEEKS_PER_MONTH = 4.33

SCENARIOS = ("upside", "base", "downside")


def _week_index(start: datetime, when: datetime, horizon: int) -> int | None:
    """Week bucket (0-based) for ``when``; None if outside the horizon.

    Dates before the start (already-overdue inflows) land in week 0 — money
    expected 'any moment now' is this week's money, not lost money.
    """
    days = (when - start).days
    if days < 0:
        return 0
    index = days // 7
    return index if index < horizon else None


def _inflow_date(invoice: dict[str, Any], avg_late: float | None, scenario: str) -> datetime:
    due = datetime.fromisoformat(invoice["due_date"])
    if scenario == "upside":
        return due
    delay = avg_late if avg_late is not None else DEFAULT_PAY_DELAY_DAYS
    predicted = due + timedelta(days=delay)
    if scenario == "downside":
        predicted += timedelta(days=DOWNSIDE_SLIP_DAYS)
    return predicted


def project(
    *,
    start: datetime,
    opening_balance_paise: int,
    open_invoices: list[dict[str, Any]],  # {id, number, client, amount_paise, due_date}
    avg_late_by_client: dict[str, float],
    monthly_outflows: dict[str, int],  # vendor label → stable monthly paise
    horizon_weeks: int = DEFAULT_HORIZON_WEEKS,
) -> dict[str, Any]:
    weekly_outflow = round(sum(monthly_outflows.values()) / WEEKS_PER_MONTH)

    scenarios: dict[str, list[dict[str, Any]]] = {}
    for scenario in SCENARIOS:
        weeks = [
            {
                "week": w,
                "week_start": (start + timedelta(weeks=w)).date().isoformat(),
                "inflow_paise": 0,
                "outflow_paise": weekly_outflow,
                "closing_paise": 0,
                "drivers": [],
            }
            for w in range(horizon_weeks)
        ]
        for inv in open_invoices:
            avg_late = avg_late_by_client.get(inv["client_id"])
            when = _inflow_date(inv, avg_late, scenario)
            idx = _week_index(start, when, horizon_weeks)
            if idx is None:
                continue
            weeks[idx]["inflow_paise"] += inv["amount_paise"]
            weeks[idx]["drivers"].append(
                {
                    "invoice_number": inv["number"],
                    "client": inv["client"],
                    "amount_paise": inv["amount_paise"],
                    "expected": when.date().isoformat(),
                }
            )
        balance = opening_balance_paise
        for week in weeks:
            balance += week["inflow_paise"] - week["outflow_paise"]
            week["closing_paise"] = balance
        scenarios[scenario] = weeks

    gap = detect_gap(scenarios)
    return {
        "horizon_weeks": horizon_weeks,
        "opening_balance_paise": opening_balance_paise,
        "weekly_outflow_paise": weekly_outflow,
        "outflow_basis": [
            {"vendor": vendor, "monthly_paise": amount}
            for vendor, amount in sorted(
                monthly_outflows.items(), key=lambda kv: kv[1], reverse=True
            )
        ],
        "scenarios": scenarios,
        "gap": gap,
        "narrative": _narrative(scenarios, gap),
    }


def detect_gap(scenarios: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    """First week any scenario closes below zero, worst scenario first."""
    for scenario in ("downside", "base", "upside"):
        for week in scenarios[scenario]:
            if week["closing_paise"] < 0:
                late_money = [
                    d
                    for w in scenarios[scenario][week["week"] :]
                    for d in w["drivers"]
                ]
                return {
                    "scenario": scenario,
                    "week": week["week"],
                    "week_start": week["week_start"],
                    "shortfall_paise": -week["closing_paise"],
                    "delayed_inflows": late_money[:5],
                }
    return None


def _narrative(scenarios: dict[str, list[dict[str, Any]]], gap: dict[str, Any] | None) -> list[str]:
    base_end = scenarios["base"][-1]["closing_paise"]
    down_end = scenarios["downside"][-1]["closing_paise"]
    lines = [
        f"Base case ends the horizon at {format_inr(base_end)}; "
        f"the downside band ends at {format_inr(down_end)}."
    ]
    if gap is None:
        lines.append("No cash gap inside the horizon, even on the downside band.")
        return lines
    lines.append(
        f"⚠ {gap['scenario'].capitalize()} scenario goes {format_inr(gap['shortfall_paise'])} "
        f"negative in week {gap['week'] + 1} (w/c {gap['week_start']})."
    )
    if gap["delayed_inflows"]:
        top = gap["delayed_inflows"][0]
        lines.append(
            f"Largest lever: {top['client']}'s {top['invoice_number']} "
            f"({format_inr(top['amount_paise'])}), expected {top['expected']} — "
            "collecting it earlier closes most of the gap."
        )
    return lines
