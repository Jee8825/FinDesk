"""Rules-only matcher v0 — pure functions, exhaustively unit-testable.

Deliberately no LLM (roadmap Phase 1): exact-amount credit matches with date
sanity and counterparty-name corroboration. Anything ambiguous stays
unmatched — an exception for the human queue, never a guess.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

NAME_MATCH_CONFIDENCE = 0.95
UNIQUE_AMOUNT_CONFIDENCE = 0.90  # equals the commit floor: unique amount alone commits


def _name_tokens(name: str) -> set[str]:
    stop = {"pvt", "ltd", "private", "limited", "llp", "co", "company", "the", "and"}
    return {t for t in name.lower().replace(".", " ").split() if len(t) > 2 and t not in stop}


def _hint_matches(hint: str | None, narration: str, party_name: str) -> bool:
    tokens = _name_tokens(party_name)
    if not tokens:
        return False
    haystack = f"{hint or ''} {narration}".lower()
    hits = sum(1 for t in tokens if t in haystack)
    return hits >= max(1, len(tokens) // 2)


def propose_matches(
    unmatched: list[dict[str, Any]],
    open_invoices: list[dict[str, Any]],
    counterparties: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    party_names = {p["id"]: p["name"] for p in counterparties}
    taken_invoices: set[str] = set()
    proposals: list[dict[str, Any]] = []

    for txn in unmatched:
        if txn["direction"] != "cr":
            continue  # v0 matches incoming payments to AR invoices only
        txn_date = datetime.fromisoformat(txn["value_date"])

        candidates = []
        for inv in open_invoices:
            if inv["id"] in taken_invoices:
                continue
            if inv["amount_paise"] != txn["amount_paise"]:
                continue
            if txn_date.date() < datetime.fromisoformat(inv["issue_date"]).date():
                continue  # paid before it was issued — not this invoice
            named = _hint_matches(
                txn.get("counterparty_hint"),
                txn.get("narration", ""),
                party_names.get(inv["counterparty_id"], ""),
            )
            candidates.append((named, inv))

        named_candidates = [inv for named, inv in candidates if named]
        if len(named_candidates) == 1:
            chosen, confidence = named_candidates[0], NAME_MATCH_CONFIDENCE
        elif not named_candidates and len(candidates) == 1:
            chosen, confidence = candidates[0][1], UNIQUE_AMOUNT_CONFIDENCE
        else:
            continue  # zero or ambiguous → leave as exception

        taken_invoices.add(chosen["id"])
        proposals.append(
            {
                "bank_transaction_id": txn["id"],
                "invoice_id": chosen["id"],
                "counterparty_id": chosen["counterparty_id"],
                "invoice_number": chosen["number"],
                "amount_paise": txn["amount_paise"],
                "kind": "full",
                "confidence": confidence,
                "txn_date": txn["value_date"],
                "due_date": chosen["due_date"],
            }
        )
    return proposals


def critic_review(
    proposals: list[dict[str, Any]], open_invoices: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Independent deterministic re-check; the LLM Critic lands in Phase 2."""
    open_by_id = {inv["id"]: inv for inv in open_invoices}
    seen_txns: set[str] = set()
    seen_invoices: set[str] = set()
    reviewed = []
    for p in proposals:
        problems = []
        inv = open_by_id.get(p["invoice_id"])
        if inv is None:
            problems.append("invoice not open")
        elif inv["amount_paise"] != p["amount_paise"]:
            problems.append("amount mismatch")
        if p["bank_transaction_id"] in seen_txns:
            problems.append("duplicate transaction in batch")
        if p["invoice_id"] in seen_invoices:
            problems.append("duplicate invoice in batch")
        seen_txns.add(p["bank_transaction_id"])
        seen_invoices.add(p["invoice_id"])
        reviewed.append(
            {
                **p,
                "critic_verdict": {
                    "verdict": "pass" if not problems else "fail",
                    "problems": problems,
                    "checker": "deterministic-v0",
                },
            }
        )
    return reviewed
