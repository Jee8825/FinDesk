"""Rules matcher — pure functions, exhaustively unit-testable.

Phase 1: exact-amount credit matches with date sanity and counterparty-name
corroboration. Phase 2 adds **TDS-adjusted** matching: a payment that equals
an open invoice minus tax-deducted-at-source. TDS proposals always price in
below the commit floor, so they route to the human approval queue — the agent
recommends, a human posts. Remembered deduction patterns (Recall memory) rank
above standard-rate guesses. Anything ambiguous stays unmatched.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

NAME_MATCH_CONFIDENCE = 0.95
UNIQUE_AMOUNT_CONFIDENCE = 0.90  # equals the commit floor: unique amount alone commits
TDS_REMEMBERED_CONFIDENCE = 0.85  # memory-corroborated rate → strong but human-gated
TDS_STANDARD_RATE_CONFIDENCE = 0.80  # plausible standard rate, name-matched only

# Common TDS rates in basis points: 194C 1%/2%, 194J/194H 5%/10%
STANDARD_TDS_BPS = (100, 200, 500, 1000)

_RATE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*TDS|TDS\s*(?:of|at)?\s*(\d+(?:\.\d+)?)\s*%", re.I)


def parse_deduction_rates(memory_contents: list[str]) -> list[int]:
    """Extract remembered TDS rates (basis points) from memory claim texts."""
    rates: list[int] = []
    for text in memory_contents:
        for m in _RATE_RE.finditer(text):
            pct = m.group(1) or m.group(2)
            bps = round(float(pct) * 100)
            if 0 < bps <= 3000 and bps not in rates:
                rates.append(bps)
    return rates


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


def any_committable(proposals: list[dict[str, Any]]) -> bool:
    """True when at least one proposal survived the critic.

    The router's predicate, kept pure and here rather than in nodes.py so the
    branch decision is unit-testable without constructing graph state.
    """
    return any(p.get("critic_verdict", {}).get("verdict") == "pass" for p in proposals)


def vetoed_with_reasons(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The critic's findings on proposals it rejected, shaped for run evidence.

    ``services/recon.py`` discards a rejected proposal with the flat reason
    "critic rejected", so the critic's *actual* finding — often the most
    specific thing a run produced — never reaches a human. This lifts it out.
    """
    return [
        {
            "invoice_number": p.get("invoice_number"),
            "amount_paise": p.get("amount_paise"),
            "problems": p.get("critic_verdict", {}).get("problems", []),
            "checker": p.get("critic_verdict", {}).get("checker", ""),
        }
        for p in proposals
        if p.get("critic_verdict", {}).get("verdict") != "pass"
    ]


def evidence_for_review(
    proposals: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach the bank narration each proposal was derived from, plus an index.

    A proposal dict carries IDs and amounts but not the narration it came from
    (see ``propose_matches``). Two of the critic prompt's four veto criteria —
    "narration suggests a different counterparty" and "TDS rate inconsistent
    with the service the narration implies" — are unanswerable without it, so
    handing the raw proposals to the LLM asks it to judge evidence it cannot
    see. The explicit ``index`` pins the response mapping to position rather
    than relying on the model to preserve list order.

    Pure: returns new dicts, never mutates the inputs.
    """
    by_id = {t["id"]: t for t in transactions}
    return [
        {
            **p,
            "index": i,
            "narration": by_id.get(p.get("bank_transaction_id"), {}).get("narration", ""),
        }
        for i, p in enumerate(proposals)
    ]


def propose_tds_matches(
    unmatched: list[dict[str, Any]],
    open_invoices: list[dict[str, Any]],
    counterparties: list[dict[str, Any]],
    remembered_rates: dict[str, list[int]] | None = None,
) -> list[dict[str, Any]]:
    """TDS-adjusted candidates: payment == invoice − invoice×rate, to the paisa.

    Only name-corroborated candidates are proposed (an amount that merely
    happens to be 98% of some invoice is not evidence). ``remembered_rates``
    maps counterparty_id → TDS basis points learned from memory; those rank
    above standard rates.
    """
    party_names = {p["id"]: p["name"] for p in counterparties}
    remembered = remembered_rates or {}
    taken: set[str] = set()
    proposals: list[dict[str, Any]] = []

    for txn in unmatched:
        if txn["direction"] != "cr":
            continue
        txn_date = datetime.fromisoformat(txn["value_date"])
        candidates: list[tuple[float, int, dict[str, Any]]] = []  # (conf, tds_paise, invoice)

        for inv in open_invoices:
            if inv["id"] in taken:
                continue
            if txn_date.date() < datetime.fromisoformat(inv["issue_date"]).date():
                continue
            if not _hint_matches(
                txn.get("counterparty_hint"),
                txn.get("narration", ""),
                party_names.get(inv["counterparty_id"], ""),
            ):
                continue
            invoice_amount = inv["amount_paise"]
            party_rates = remembered.get(inv["counterparty_id"], [])
            for bps in [*party_rates, *STANDARD_TDS_BPS]:
                tds = invoice_amount * bps // 10_000
                if invoice_amount * bps % 10_000 != 0:
                    continue  # not an exact-paise deduction — too speculative
                if txn["amount_paise"] == invoice_amount - tds and tds > 0:
                    conf = (
                        TDS_REMEMBERED_CONFIDENCE
                        if bps in party_rates
                        else TDS_STANDARD_RATE_CONFIDENCE
                    )
                    candidates.append((conf, tds, {**inv, "tds_bps": bps}))
                    break

        if len(candidates) != 1:
            continue  # zero or ambiguous → exception queue
        conf, tds, inv = candidates[0]
        taken.add(inv["id"])
        proposals.append(
            {
                "bank_transaction_id": txn["id"],
                "invoice_id": inv["id"],
                "counterparty_id": inv["counterparty_id"],
                "invoice_number": inv["number"],
                "amount_paise": txn["amount_paise"],
                "tds_paise": tds,
                "tds_bps": inv["tds_bps"],
                "kind": "tds_adjusted",
                "confidence": conf,
                "txn_date": txn["value_date"],
                "due_date": inv["due_date"],
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
        expected = p["amount_paise"] + int(p.get("tds_paise", 0))
        if inv is None:
            problems.append("invoice not open")
        elif inv["amount_paise"] != expected:
            problems.append("amount mismatch")
        if p.get("kind") == "tds_adjusted" and int(p.get("tds_paise", 0)) <= 0:
            problems.append("tds_adjusted without tds amount")
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
