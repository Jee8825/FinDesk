"""Rules-matcher unit tests — pure logic, no I/O."""

from findesk_agents.graphs.reconciliation.matching import (
    any_committable,
    critic_review,
    evidence_for_review,
    propose_matches,
    vetoed_with_reasons,
)

PARTIES = [
    {"id": "p1", "name": "Blue Tokai Coffee Pvt Ltd", "kind": "client"},
    {"id": "p2", "name": "Origin Roasters", "kind": "client"},
]


def _txn(
    id="t1",
    amount=4_500_000,
    hint="BLUE TOKAI COFFEE",
    narration="NEFT-BLUE TOKAI-INV",
    date="2026-04-10T00:00:00+00:00",
    direction="cr",
):
    return {
        "id": id,
        "value_date": date,
        "amount_paise": amount,
        "direction": direction,
        "narration": narration,
        "counterparty_hint": hint,
    }


def _inv(
    id="i1",
    party="p1",
    amount=4_500_000,
    number="INV-42",
    issue="2026-04-01T00:00:00+00:00",
    due="2026-04-30T00:00:00+00:00",
):
    return {
        "id": id,
        "counterparty_id": party,
        "number": number,
        "issue_date": issue,
        "due_date": due,
        "amount_paise": amount,
    }


def test_named_match_wins_with_high_confidence():
    proposals = propose_matches([_txn()], [_inv()], PARTIES)
    assert len(proposals) == 1
    assert proposals[0]["confidence"] == 0.95
    assert proposals[0]["invoice_id"] == "i1"


def test_ambiguous_same_amount_without_name_stays_unmatched():
    invoices = [_inv(id="i1", party="p1"), _inv(id="i2", party="p2", number="INV-43")]
    txn = _txn(hint=None, narration="NEFT-SOMEBODY-PAY")
    assert propose_matches([txn], invoices, PARTIES) == []


def test_unique_amount_without_name_matches_at_floor():
    proposals = propose_matches(
        [_txn(hint=None, narration="IMPS TRANSFER")], [_inv()], PARTIES
    )
    assert len(proposals) == 1
    assert proposals[0]["confidence"] == 0.90


def test_debits_and_pre_issue_payments_skipped():
    assert propose_matches([_txn(direction="dr")], [_inv()], PARTIES) == []
    early = _txn(date="2026-03-20T00:00:00+00:00")
    assert propose_matches([early], [_inv()], PARTIES) == []


def test_one_invoice_never_matched_twice():
    txns = [_txn(id="t1"), _txn(id="t2")]
    proposals = propose_matches(txns, [_inv()], PARTIES)
    assert len(proposals) == 1


def test_critic_flags_closed_invoice_and_duplicates():
    proposals = propose_matches([_txn()], [_inv()], PARTIES)
    reviewed = critic_review(proposals, [])  # invoice no longer open
    assert reviewed[0]["critic_verdict"]["verdict"] == "fail"
    assert "invoice not open" in reviewed[0]["critic_verdict"]["problems"]

    ok = critic_review(proposals, [_inv()])
    assert ok[0]["critic_verdict"]["verdict"] == "pass"

    dupes = critic_review(proposals + proposals, [_inv()])
    assert dupes[1]["critic_verdict"]["verdict"] == "fail"


def test_evidence_for_review_attaches_narration_and_index():
    """The critic cannot judge narration it was never sent (regression)."""
    proposals = [
        {"bank_transaction_id": "txn-1", "invoice_number": "INV-1"},
        {"bank_transaction_id": "txn-2", "invoice_number": "INV-2"},
    ]
    txns = [
        {"id": "txn-1", "narration": "NEFT FROM ZENITH TRADERS"},
        {"id": "txn-2", "narration": "NEFT FROM ACME CORP"},
    ]
    out = evidence_for_review(proposals, txns)

    assert [p["narration"] for p in out] == ["NEFT FROM ZENITH TRADERS", "NEFT FROM ACME CORP"]
    assert [p["index"] for p in out] == [0, 1], "index must pin response mapping to position"
    assert out[0]["invoice_number"] == "INV-1", "original fields survive"
    assert "narration" not in proposals[0], "must not mutate the caller's proposals"


def test_evidence_for_review_tolerates_a_missing_transaction():
    out = evidence_for_review([{"bank_transaction_id": "gone"}], [])
    assert out[0]["narration"] == "", "absent txn degrades to empty, never raises"


# --- critic routing predicates (the recon graph's one real branch) -----------

def _p(verdict, **kw):
    return {"critic_verdict": {"verdict": verdict, **kw.pop("cv", {})}, **kw}


def test_any_committable_true_when_one_proposal_passes():
    assert any_committable([_p("fail"), _p("pass")]) is True


def test_any_committable_false_when_all_vetoed():
    assert any_committable([_p("fail"), _p("fail")]) is False


def test_any_committable_false_on_empty_and_on_missing_verdict():
    assert any_committable([]) is False
    assert any_committable([{}]) is False, "a proposal with no verdict is not committable"


def test_vetoed_with_reasons_carries_the_critics_finding():
    proposals = [
        _p("pass", invoice_number="INV-1", amount_paise=100),
        _p(
            "fail",
            invoice_number="INV-2",
            amount_paise=200,
            cv={"problems": ["llm: narration names a different company"],
                "checker": "deterministic-v0+llm:groq:llama-3.3-70b-versatile"},
        ),
    ]
    out = vetoed_with_reasons(proposals)

    assert len(out) == 1, "passes are not findings"
    assert out[0]["invoice_number"] == "INV-2"
    assert out[0]["problems"] == ["llm: narration names a different company"]
    # provenance travels with the finding — a human sees *who* vetoed it
    assert "groq:llama-3.3-70b-versatile" in out[0]["checker"]


def test_vetoed_with_reasons_tolerates_a_bare_verdict():
    out = vetoed_with_reasons([_p("fail", invoice_number="INV-3")])
    assert out[0]["problems"] == [] and out[0]["checker"] == ""
