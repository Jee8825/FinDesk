"""LeakRadar critic — deterministic invariants between scoring and persistence.

The Critic seat made concrete, same posture as the forecast critic: pure checks
that must hold for ANY correct scan, independent of inputs. A violation means the
engine or its wiring is broken, and persisting would put plausible-looking
nonsense in front of someone about to cancel a real service — so the run fails
loudly instead.

NO LLM TOUCHES THIS MODULE.
"""

from __future__ import annotations

from typing import Any


def review(rows: list[dict[str, Any]], totals: dict[str, Any]) -> list[str]:
    """Return violations (empty = pass). Pure."""
    problems: list[str] = []

    for r in rows:
        label = r.get("vendor_label") or r.get("vendor_slug") or "?"

        # money must always rank. The converse is fine: advisory signals (an
        # upcoming renewal, overlapping services) score with nothing recoverable.
        if r["recoverable_paise_per_year"] > 0 and r["leak_score"] <= 0:
            problems.append(f"{label}: recoverable money with a zero leak score")

        if r["recoverable_paise_per_year"] < 0:
            problems.append(f"{label}: negative recoverable amount")
        if not 0 <= r["leak_score"] <= 100:
            problems.append(f"{label}: leak score {r['leak_score']} out of range")

        # a stopped series is not a leak, and a commitment is not a subscription
        if r["status"] == "stopped" and r["recoverable_paise_per_year"] > 0:
            problems.append(f"{label}: stopped series claims recoverable money")
        if r["drift_kind"] == "excluded" and r["leak_score"] > 0:
            problems.append(f"{label}: excluded category scored above zero")

        # run-rate must reconcile with cadence × latest amount
        per_year = r.get("periods_per_year")
        if per_year and r["run_rate_paise"] != r["latest_amount_paise"] * per_year:
            problems.append(f"{label}: run rate does not reconcile with cadence")

        # never claim back more than the thing costs, unless a duplicate charge
        # explains the excess
        ceiling = r["run_rate_paise"] + r["duplicate_paise"]
        if r["run_rate_paise"] and r["recoverable_paise_per_year"] > ceiling:
            problems.append(f"{label}: recoverable exceeds annual cost")

    active = [r for r in rows if r["status"] == "active"]
    if totals.get("subscriptions") != len(active):
        problems.append("totals: active count disagrees with rows")
    if totals.get("recoverable_paise_per_year") != sum(
        r["recoverable_paise_per_year"] for r in active
    ):
        problems.append("totals: recoverable sum disagrees with rows")

    return problems
