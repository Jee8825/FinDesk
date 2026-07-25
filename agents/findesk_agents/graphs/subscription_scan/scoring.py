"""Leak scoring — a 0-100 score and, more usefully, a rupee figure.

Two numbers per subscription, deliberately:

* ``recoverable_paise_per_year`` — money you could actually get back. Kept
  *conservative*: an unapproved price rise and a duplicate charge are recoverable
  because they are evidenced. The full subscription cost is NOT counted as
  recoverable merely because the tool suspects disuse — bank data cannot know
  whether anyone logged in. It becomes recoverable only once a human tells us the
  thing is unused, which is what the confirmation loop is for.
* ``leak_score`` — 0-100, for ranking and because the brief asks for a score.
  Never shown without its components; a score nobody can interrogate is a score
  nobody will act on.

Exclusions matter as much as detection here. Rent, payroll and tax payments are
the largest recurring debits in most books and none of them is a subscription
leak. A tool that tells a founder their biggest leak is salaries has failed.

Pure and deterministic. NO LLM TOUCHES THIS MODULE.
"""

from __future__ import annotations

from typing import Any

# Recurring, but commitments rather than discretionary subscriptions. Scored at
# zero and surfaced separately so the user can see we know they exist.
EXCLUDED_CATEGORIES_BUSINESS = frozenset(
    {"payroll", "rent", "taxes_tds", "taxes_gst", "taxes", "loan_emi", "statutory"}
)
EXCLUDED_CATEGORIES_PERSONAL = frozenset(
    {"rent", "loan_emi", "insurance", "investment", "taxes"}
)

# Signal weights, summing to 100 before the magnitude adjustment.
W_DRIFT = 30
W_DUPLICATE = 25
W_UNUSED = 15
W_REDUNDANCY = 15
W_RENEWAL = 15

# A +25% rise or worse saturates the drift signal.
DRIFT_SATURATION = 0.25
# ₹1,00,000/year of run-rate saturates the magnitude adjustment.
MAGNITUDE_CEILING_PAISE = 10_000_000
# Floor so a small-but-clear leak still scores: magnitude scales, never erases.
MAGNITUDE_FLOOR = 0.4
# An annual renewal this close is actionable *now*.
RENEWAL_HORIZON_DAYS = 60


def excluded_categories(mode: str) -> frozenset[str]:
    return (
        EXCLUDED_CATEGORIES_PERSONAL
        if mode == "personal"
        else EXCLUDED_CATEGORIES_BUSINESS
    )


def run_rate_paise(cadence: dict[str, Any]) -> int:
    """Annualized cost at the current price. 0 for irregular/unknown cadence."""
    per_year = cadence.get("periods_per_year")
    if not per_year:
        return 0
    return cadence["latest_amount_paise"] * per_year


def score_one(
    cadence: dict[str, Any],
    drift: dict[str, Any],
    *,
    mode: str = "business",
    duplicate_paise: int = 0,
    category_peers: int = 1,
    usage: str | None = None,
) -> dict[str, Any]:
    """Score one subscription.

    ``usage`` is the human's answer, when we have one: "in_use", "unused", or
    None for never asked. It is the only thing that licenses counting the whole
    subscription as recoverable.
    """
    category = cadence.get("category_code")
    run_rate = run_rate_paise(cadence)

    if cadence.get("status") == "stopped":
        return _zero(
            cadence, drift, run_rate,
            reason="Already stopped — no charge since "
                   f"{cadence['last_seen'][:10]}.",
            kind="stopped",
        )
    if category in excluded_categories(mode):
        return _zero(
            cadence, drift, run_rate,
            reason=f"Recurring {category.replace('_', ' ')} commitment, not a "
                   "discretionary subscription.",
            kind="excluded",
        )

    drift_extra = max(0, drift.get("annualized_extra_paise", 0))
    drift_pct = abs((drift.get("step_change") or {}).get("pct", 0.0))
    unused = usage == "unused"
    renewal_due = (
        cadence.get("cadence") == "annual"
        and 0 <= (cadence.get("days_until_next") or 999) <= RENEWAL_HORIZON_DAYS
    )

    components = {
        "drift": round(W_DRIFT * min(1.0, drift_pct / DRIFT_SATURATION), 1),
        "duplicate": float(W_DUPLICATE if duplicate_paise > 0 else 0),
        "unused": float(W_UNUSED if unused else 0),
        "redundancy": round(W_REDUNDANCY * min(1.0, max(0, category_peers - 1) / 2), 1),
        "renewal": float(W_RENEWAL if renewal_due else 0),
    }
    base = sum(components.values())
    magnitude = min(1.0, run_rate / MAGNITUDE_CEILING_PAISE) if run_rate else 0.0
    score = round(base * (MAGNITUDE_FLOOR + (1 - MAGNITUDE_FLOOR) * magnitude))

    # Conservative by construction: evidenced money only, unless a human has
    # told us the subscription is dead.
    recoverable = drift_extra + duplicate_paise + (run_rate if unused else 0)

    return {
        "vendor_slug": cadence.get("vendor_slug"),
        "vendor_label": cadence.get("vendor_label"),
        "category_code": category,
        "cadence": cadence.get("cadence"),
        "status": cadence.get("status"),
        "run_rate_paise": run_rate,
        "leak_score": min(100, score),
        "score_components": components,
        "recoverable_paise_per_year": recoverable,
        "drift_paise_per_year": drift_extra,
        "duplicate_paise": duplicate_paise,
        "category_peers": category_peers,
        "usage": usage,
        "renewal_due": renewal_due,
        "drift_kind": drift.get("kind"),
        "reason": drift.get("note", ""),
        "recommended_action": recommend(
            drift, unused=unused, renewal_due=renewal_due, peers=category_peers
        ),
    }


def _zero(cadence, drift, run_rate, *, reason, kind) -> dict[str, Any]:
    return {
        "vendor_slug": cadence.get("vendor_slug"),
        "vendor_label": cadence.get("vendor_label"),
        "category_code": cadence.get("category_code"),
        "cadence": cadence.get("cadence"),
        "status": cadence.get("status"),
        "run_rate_paise": run_rate,
        "leak_score": 0,
        "score_components": {},
        "recoverable_paise_per_year": 0,
        "drift_paise_per_year": 0,
        "duplicate_paise": 0,
        "category_peers": 1,
        "usage": None,
        "renewal_due": False,
        "drift_kind": kind,
        "reason": reason,
        "recommended_action": "No action — informational only.",
    }


def recommend(
    drift: dict[str, Any], *, unused: bool, renewal_due: bool, peers: int
) -> str:
    """The action, chosen deterministically. Wording may later be LLM-polished;
    the choice never is."""
    if unused:
        return "Cancel — you confirmed this is no longer used."
    kind = drift.get("kind")
    if kind == "seat_creep":
        return "Reconcile seats against headcount, then downgrade unused seats."
    if kind == "price_increase":
        return "Renegotiate or downgrade — the increase was never approved."
    if renewal_due:
        return "Review before it auto-renews — the annual charge is due soon."
    if peers > 1:
        return f"Consolidate — {peers} active subscriptions share this category."
    if kind == "usage_based":
        return "Usage-based — set a budget alert rather than cancelling."
    return "Keep — no leak signal detected."


def rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Highest recoverable money first, then score, then run-rate.

    Money leads deliberately: the score sorts comparable rows, but between a
    90-score on ₹600/year and a 60-score on ₹80,000/year the second is the one
    to act on this afternoon.
    """
    return sorted(
        rows,
        key=lambda r: (
            -r["recoverable_paise_per_year"],
            -r["leak_score"],
            -r["run_rate_paise"],
        ),
    )


def portfolio_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Headline numbers, plus category-wise annualized cost for the chart."""
    active = [r for r in rows if r["status"] == "active"]
    by_category: dict[str, int] = {}
    for r in active:
        key = r["category_code"] or "uncategorized"
        by_category[key] = by_category.get(key, 0) + r["run_rate_paise"]
    return {
        "subscriptions": len(active),
        "stopped": sum(1 for r in rows if r["status"] == "stopped"),
        "committed_paise_per_year": sum(r["run_rate_paise"] for r in active),
        "recoverable_paise_per_year": sum(
            r["recoverable_paise_per_year"] for r in active
        ),
        "drift_paise_per_year": sum(r["drift_paise_per_year"] for r in active),
        "leaking_count": sum(1 for r in active if r["recoverable_paise_per_year"] > 0),
        "unreviewed_count": sum(1 for r in active if r["usage"] is None),
        "by_category_paise": dict(
            sorted(by_category.items(), key=lambda kv: -kv[1])
        ),
    }
