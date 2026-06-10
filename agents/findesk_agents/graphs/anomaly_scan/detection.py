"""A6 anomaly detection — pure functions over debit history.

Three detectors, all deterministic and explainable:

* **duplicate** — same vendor slug, same amount, within DUPLICATE_WINDOW_DAYS.
  The classic double-payment; the later transaction is recoverable money.
* **overcharge** — a recurring vendor (≥ MIN_BASELINE_POINTS prior amounts,
  stable within BASELINE_STABILITY) suddenly bills ≥ OVERCHARGE_FACTOR × its
  baseline. The delta is flagged recoverable pending review.
* **out_of_pattern** — a recurring vendor deviates above the baseline but
  below the overcharge factor; informational severity, no recoverable amount.

Memory baselines (``anomaly_baseline`` claims) extend the in-window history so
the scan stays sharp even when older statements have aged out of the books.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from statistics import median
from typing import Any

from findesk_shared import vendor_slug as _shared_slug

DUPLICATE_WINDOW_DAYS = 7
MIN_BASELINE_POINTS = 2
BASELINE_STABILITY = 0.25  # max relative spread for a baseline to count as stable
OVERCHARGE_FACTOR = 1.5
OUT_OF_PATTERN_FACTOR = 1.25


def slug(txn: dict[str, Any]) -> str:
    return _shared_slug(txn.get("counterparty_hint"), txn.get("narration", ""))


def _date(txn: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(txn["value_date"])


def _dedupe_key(kind: str, *parts: str) -> str:
    return hashlib.sha256("|".join([kind, *parts]).encode()).hexdigest()


def detect_duplicates(debits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    by_key: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for t in debits:
        by_key.setdefault((slug(t), t["amount_paise"]), []).append(t)
    for (_vendor, amount), txns in by_key.items():
        txns.sort(key=_date)
        for first, second in zip(txns, txns[1:], strict=False):
            gap = (_date(second) - _date(first)).days
            if gap <= DUPLICATE_WINDOW_DAYS:
                findings.append(
                    {
                        "kind": "duplicate",
                        "severity": "high",
                        "vendor_label": (
                            second.get("counterparty_hint") or second["narration"][:40]
                        ),
                        "evidence": {
                            "first_txn_id": first["id"],
                            "second_txn_id": second["id"],
                            "amount_paise": amount,
                            "days_apart": gap,
                            "narrations": [first["narration"], second["narration"]],
                        },
                        "recommended_action": (
                            "Possible double payment — verify with the vendor and "
                            "recover the second debit."
                        ),
                        "recoverable_paise": amount,
                        "dedupe_key": _dedupe_key("duplicate", first["id"], second["id"]),
                    }
                )
    return findings


def _stable_baseline(amounts: list[int]) -> int | None:
    if len(amounts) < MIN_BASELINE_POINTS:
        return None
    base = int(median(amounts))
    if base <= 0:
        return None
    spread = (max(amounts) - min(amounts)) / base
    return base if spread <= BASELINE_STABILITY else None


def detect_deviations(
    debits: list[dict[str, Any]],
    memory_baselines: dict[str, list[int]] | None = None,
) -> list[dict[str, Any]]:
    """Overcharge / out-of-pattern against each vendor's stable baseline."""
    memory_baselines = memory_baselines or {}
    findings = []
    by_vendor: dict[str, list[dict[str, Any]]] = {}
    for t in debits:
        by_vendor.setdefault(slug(t), []).append(t)

    for vendor, txns in by_vendor.items():
        txns.sort(key=_date)
        latest = txns[-1]
        history = [t["amount_paise"] for t in txns[:-1]] + memory_baselines.get(vendor, [])
        baseline = _stable_baseline(history)
        if baseline is None or latest["amount_paise"] <= baseline:
            continue
        ratio = latest["amount_paise"] / baseline
        if ratio >= OVERCHARGE_FACTOR:
            kind, severity = "overcharge", "high"
            recoverable = latest["amount_paise"] - baseline
            action = (
                f"Bill is {ratio:.1f}× the usual amount — dispute the overcharge "
                "or confirm a plan change."
            )
        elif ratio >= OUT_OF_PATTERN_FACTOR:
            kind, severity = "out_of_pattern", "medium"
            recoverable = None
            action = "Spend is above this vendor's pattern — worth a look."
        else:
            continue
        findings.append(
            {
                "kind": kind,
                "severity": severity,
                "vendor_label": latest.get("counterparty_hint") or latest["narration"][:40],
                "evidence": {
                    "txn_id": latest["id"],
                    "amount_paise": latest["amount_paise"],
                    "baseline_paise": baseline,
                    "history_points": len(history),
                    "ratio": round(ratio, 2),
                },
                "recommended_action": action,
                "recoverable_paise": recoverable,
                "dedupe_key": _dedupe_key(kind, vendor, latest["id"]),
            }
        )
    return findings


def baseline_claims(debits: list[dict[str, Any]]) -> dict[str, int]:
    """Vendors with a stable spend baseline worth remembering."""
    by_vendor: dict[str, list[int]] = {}
    labels: dict[str, str] = {}
    for t in debits:
        v = slug(t)
        by_vendor.setdefault(v, []).append(t["amount_paise"])
        labels.setdefault(v, t.get("counterparty_hint") or t["narration"][:40])
    out = {}
    for vendor, amounts in by_vendor.items():
        base = _stable_baseline(amounts)
        if base is not None:
            out[vendor] = base
    return out
