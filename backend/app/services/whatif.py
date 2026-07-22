"""Scenario sandbox math — deterministic what-if over stored forecast lines.

Pure functions only: no I/O, no LLM, no floats touching money. The UI is
forbidden from computing financial values (frontend rule #4); this is the
server-side truth it renders. All adjustments operate on the persisted
base-scenario weekly buckets of the latest forecast.
"""

from __future__ import annotations

from typing import Any, TypedDict


class WhatifParams(TypedDict, total=False):
    collection_delay_days: int  # -30..60 — clients pay later (or earlier)
    inflow_haircut_bps: int  # 0..5000 — % of expected inflows that vanish
    extra_monthly_outflow_paise: int  # >=0 — e.g. a new hire


def clamp_params(raw: dict[str, Any]) -> WhatifParams:
    """Coerce + clamp untrusted input into safe bounds."""

    def _int(name: str, lo: int, hi: int) -> int:
        try:
            v = int(raw.get(name, 0))
        except (TypeError, ValueError):
            v = 0
        return max(lo, min(hi, v))

    return WhatifParams(
        collection_delay_days=_int("collection_delay_days", -30, 60),
        inflow_haircut_bps=_int("inflow_haircut_bps", 0, 5000),
        extra_monthly_outflow_paise=_int("extra_monthly_outflow_paise", 0, 10_000_000_000),
    )


def apply_whatif(
    base_weeks: list[dict[str, Any]],
    opening_balance_paise: int,
    params: WhatifParams,
) -> dict[str, Any]:
    """Recompute weekly closings under the adjusted assumptions.

    Weekly buckets: a collection delay shifts inflows whole weeks
    (round(days/7)); inflows pushed past the horizon drop out (reported as
    pushed_out_paise). Haircut trims every inflow in basis points. Extra
    monthly outflow spreads as ``* 12 // 52`` per week. Closings re-run
    cumulatively from the same opening balance; the first negative week is
    the gap.
    """
    if not base_weeks:
        return {"weeks": [], "gap": None, "pushed_out_paise": 0, "end_delta_paise": 0}

    delay_weeks = round(params.get("collection_delay_days", 0) / 7)
    haircut_bps = params.get("inflow_haircut_bps", 0)
    extra_weekly = params.get("extra_monthly_outflow_paise", 0) * 12 // 52

    n = len(base_weeks)
    inflows = [0] * n
    pushed_out = 0
    for i, week in enumerate(base_weeks):
        inflow = int(week["inflow_paise"])
        inflow -= inflow * haircut_bps // 10_000
        j = i + delay_weeks
        if 0 <= j < n:
            inflows[j] += inflow
        elif j >= n:
            pushed_out += inflow
        else:  # negative shift walks off the front — realize immediately
            inflows[0] += inflow

    weeks: list[dict[str, Any]] = []
    gap: dict[str, Any] | None = None
    closing = opening_balance_paise
    for i, week in enumerate(base_weeks):
        outflow = int(week["outflow_paise"]) + extra_weekly
        closing = closing + inflows[i] - outflow
        weeks.append(
            {
                "week": week["week"],
                "week_start": week["week_start"],
                "inflow_paise": inflows[i],
                "outflow_paise": outflow,
                "closing_paise": closing,
                "drivers": [],
            }
        )
        if gap is None and closing < 0:
            gap = {
                "scenario": "whatif",
                "week": week["week"],
                "week_start": week["week_start"],
                "shortfall_paise": -closing,
            }

    end_delta = weeks[-1]["closing_paise"] - int(base_weeks[-1]["closing_paise"])
    return {
        "weeks": weeks,
        "gap": gap,
        "pushed_out_paise": pushed_out,
        "end_delta_paise": end_delta,
    }
