#!/usr/bin/env python3
"""Reconciliation eval harness v1 — accuracy as a number, not an assertion.

Runs the matcher (exact + TDS) against a golden set of labeled scenarios and
reports precision / recall / F1 over proposed (txn → invoice) pairs, plus
guardrail checks (ambiguity refusal, debit refusal, critic tamper detection).
Exits non-zero if any metric drops below the floors — CI treats that as a
regression. Results are written to evals_out/recon_eval.json (publishable
in-product per the spec's calibration promise).

Usage: .venv/bin/python infra/observability/evals/run_recon_eval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "agents"))

from findesk_agents.graphs.reconciliation.matching import (  # noqa: E402
    critic_review,
    propose_matches,
    propose_tds_matches,
)

FLOORS = {"precision": 1.0, "recall": 0.85, "guardrails": 1.0}

PARTIES = [
    {"id": "p1", "name": "Blue Tokai Coffee Pvt Ltd", "kind": "client"},
    {"id": "p2", "name": "Origin Roasters Pvt Ltd", "kind": "client"},
    {"id": "p3", "name": "Chai Point Retail", "kind": "client"},
]


def txn(id: str, amount: int, narration: str, hint: str | None, date: str = "2026-04-10") -> dict:
    return {
        "id": id,
        "value_date": f"{date}T00:00:00+00:00",
        "amount_paise": amount,
        "direction": "cr",
        "narration": narration,
        "counterparty_hint": hint,
    }


def inv(id: str, party: str, number: str, amount: int, issue: str = "2026-03-20") -> dict:
    return {
        "id": id,
        "counterparty_id": party,
        "number": number,
        "issue_date": f"{issue}T00:00:00+00:00",
        "due_date": "2026-04-30T00:00:00+00:00",
        "amount_paise": amount,
    }


# Each case: inputs + the exact set of (txn, invoice, kind) pairs a correct
# matcher must propose. Pairs NOT listed must not be proposed.
GOLDEN: list[dict[str, Any]] = [
    {
        "name": "named exact matches",
        "txns": [
            txn("t1", 4_500_000, "NEFT-BLUE TOKAI COFFEE-INV041", "BLUE TOKAI COFFEE"),
            txn("t2", 11_800_000, "IMPS-ORIGIN ROASTERS PVT LTD-PAY", "ORIGIN ROASTERS PVT LTD"),
        ],
        "invoices": [
            inv("i1", "p1", "INV-41", 4_500_000),
            inv("i2", "p2", "INV-42", 11_800_000),
        ],
        "expected": {("t1", "i1", "full"), ("t2", "i2", "full")},
    },
    {
        "name": "unique amount without name",
        "txns": [txn("t1", 3_975_000, "IMPS TRANSFER CREDIT", None)],
        "invoices": [inv("i1", "p3", "INV-48", 3_975_000)],
        "expected": {("t1", "i1", "full")},
    },
    {
        "name": "ambiguous same-amount refused",
        "txns": [txn("t1", 6_000_000, "NEFT PAYMENT RECEIVED", None)],
        "invoices": [inv("i1", "p1", "INV-49", 6_000_000), inv("i2", "p2", "INV-50", 6_000_000)],
        "expected": set(),
    },
    {
        "name": "TDS 2% standard rate (hero case)",
        "txns": [txn("t1", 4_410_000, "NEFT-BLUE TOKAI COFFEE-PAY", "BLUE TOKAI COFFEE")],
        "invoices": [inv("i1", "p1", "INV-53", 4_500_000)],
        "expected": {("t1", "i1", "tds_adjusted")},
    },
    {
        "name": "TDS remembered 5% rate",
        "txns": [txn("t1", 19_000_000, "NEFT-BLUE TOKAI COFFEE-PAY JUN", "BLUE TOKAI COFFEE")],
        "invoices": [inv("i1", "p1", "INV-54", 20_000_000)],
        "remembered": {"p1": [500]},
        "expected": {("t1", "i1", "tds_adjusted")},
    },
    {
        "name": "TDS without name corroboration refused",
        "txns": [txn("t1", 4_410_000, "IMPS TRANSFER", None)],
        "invoices": [inv("i1", "p1", "INV-53", 4_500_000)],
        "expected": set(),
    },
    {
        "name": "pre-issue payment refused",
        "txns": [txn("t1", 4_500_000, "NEFT-BLUE TOKAI-ADV", "BLUE TOKAI", date="2026-03-01")],
        "invoices": [inv("i1", "p1", "INV-53", 4_500_000, issue="2026-03-20")],
        "expected": set(),
    },
]


def run_case(case: dict[str, Any]) -> tuple[set, set]:
    exact = propose_matches(case["txns"], case["invoices"], PARTIES)
    matched_txns = {p["bank_transaction_id"] for p in exact}
    matched_invs = {p["invoice_id"] for p in exact}
    tds = propose_tds_matches(
        [t for t in case["txns"] if t["id"] not in matched_txns],
        [i for i in case["invoices"] if i["id"] not in matched_invs],
        PARTIES,
        case.get("remembered"),
    )
    proposed = {
        (p["bank_transaction_id"], p["invoice_id"], p["kind"]) for p in [*exact, *tds]
    }
    return proposed, case["expected"]


def guardrail_checks() -> dict[str, bool]:
    base_txn = txn("t1", 4_410_000, "NEFT-BLUE TOKAI-PAY", "BLUE TOKAI COFFEE")
    base_inv = inv("i1", "p1", "INV-53", 4_500_000)
    proposals = propose_tds_matches([base_txn], [base_inv], PARTIES)
    tampered = [{**proposals[0], "tds_paise": 1}]
    closed_book = critic_review(proposals, [])
    return {
        "tds_confidence_below_floor": all(p["confidence"] < 0.9 for p in proposals),
        "critic_rejects_tampered_balance": critic_review(tampered, [base_inv])[0][
            "critic_verdict"
        ]["verdict"]
        == "fail",
        "critic_rejects_closed_invoice": closed_book[0]["critic_verdict"]["verdict"] == "fail",
    }


def main() -> int:
    tp = fp = fn = 0
    case_results = []
    for case in GOLDEN:
        proposed, expected = run_case(case)
        tp += len(proposed & expected)
        fp += len(proposed - expected)
        fn += len(expected - proposed)
        ok = proposed == expected
        case_results.append({"case": case["name"], "ok": ok})
        print(f"  {'PASS' if ok else 'FAIL'}  {case['name']}")

    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    guardrails = guardrail_checks()
    for name, ok in guardrails.items():
        print(f"  {'PASS' if ok else 'FAIL'}  guardrail: {name}")
    guardrail_score = sum(guardrails.values()) / len(guardrails)

    report = {
        "suite": "reconciliation-v1",
        "cases": case_results,
        "metrics": {
            "precision": precision,
            "recall": recall,
            "f1": round(f1, 4),
            "guardrails": guardrail_score,
        },
        "floors": FLOORS,
    }
    out_dir = Path(__file__).parent / "evals_out"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "recon_eval.json").write_text(json.dumps(report, indent=2))

    print(
        f"\nprecision={precision:.3f} recall={recall:.3f} f1={f1:.3f} "
        f"guardrails={guardrail_score:.2f}"
    )
    failed = [
        m for m, floor in FLOORS.items() if report["metrics"][m] < floor
    ]
    if failed:
        print(f"REGRESSION: below floor: {failed}")
        return 1
    print("all floors met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
