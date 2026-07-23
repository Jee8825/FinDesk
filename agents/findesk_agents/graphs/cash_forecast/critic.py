"""Forecast critic — deterministic invariants between project and persist.

The Critic seat in Planner→Executor→Critic→Approval, made concrete: pure
checks that must hold for ANY correct projection, independent of inputs. A
violation means the engine (or its wiring) is broken — persisting would write
plausible-looking garbage into the books' forward view, which is worse than
failing loudly. NO LLM TOUCHES THIS MODULE.
"""

from __future__ import annotations

from typing import Any

from findesk_agents.graphs.cash_forecast.engine import SCENARIOS


def review(result: dict[str, Any]) -> list[str]:
    """Return violations (empty = pass). Pure."""
    problems: list[str] = []
    scenarios = result.get("scenarios") or {}
    horizon = result.get("horizon_weeks", 0)
    opening = result.get("opening_balance_paise", 0)

    for name in SCENARIOS:
        weeks = scenarios.get(name)
        if not weeks:
            problems.append(f"{name}: scenario missing or empty")
            continue
        if len(weeks) != horizon:
            problems.append(f"{name}: {len(weeks)} weeks, expected {horizon}")
        balance = opening
        for w in weeks:
            if w["inflow_paise"] < 0 or w["outflow_paise"] < 0:
                problems.append(f"{name} w{w['week']}: negative flow")
            balance += w["inflow_paise"] - w["outflow_paise"]
            if w["closing_paise"] != balance:
                problems.append(
                    f"{name} w{w['week']}: closing {w['closing_paise']} breaks "
                    f"continuity (expected {balance})"
                )
                balance = w["closing_paise"]  # report once per break, not per week

    # inflow conservation: timing shifts between scenarios, totals must not.
    # (dated bill outflows are identical across scenarios by construction, but
    # horizon-edge truncation can differ — inflows shifted beyond the horizon
    # legitimately shrink a scenario's total, so compare only when untruncated:
    # every scenario totalling the same as upside means nothing fell off.)
    if all(scenarios.get(s) for s in SCENARIOS):
        totals = {
            s: sum(w["inflow_paise"] for w in scenarios[s]) for s in SCENARIOS
        }
        if totals["base"] > totals["upside"] or totals["downside"] > totals["base"]:
            # later timing can only push money OUT of the window, never in
            problems.append(
                f"inflow totals inverted: upside {totals['upside']} "
                f"base {totals['base']} downside {totals['downside']}"
            )

    gap = result.get("gap")
    if gap is not None:
        weeks = scenarios.get(gap.get("scenario"), [])
        if not any(w["week"] == gap.get("week") and w["closing_paise"] < 0 for w in weeks):
            problems.append("gap points at a week that is not negative")

    return problems
