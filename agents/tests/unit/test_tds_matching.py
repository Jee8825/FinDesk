"""TDS-adjusted matcher unit tests — the spec's hero case, pure logic."""

from findesk_agents.graphs.reconciliation.matching import (
    critic_review,
    parse_deduction_rates,
    propose_tds_matches,
)

PARTIES = [{"id": "p1", "name": "Blue Tokai Coffee Pvt Ltd", "kind": "client"}]


def _txn(amount, hint="BLUE TOKAI COFFEE", narration="NEFT-BLUE TOKAI COFFEE-PAY"):
    return {
        "id": "t1",
        "value_date": "2026-05-10T00:00:00+00:00",
        "amount_paise": amount,
        "direction": "cr",
        "narration": narration,
        "counterparty_hint": hint,
    }


def _inv(amount=4_500_000, id="i1"):
    return {
        "id": id,
        "counterparty_id": "p1",
        "number": "INV-2026-053",
        "issue_date": "2026-04-25T00:00:00+00:00",
        "due_date": "2026-05-25T00:00:00+00:00",
        "amount_paise": amount,
    }


def test_hero_case_44100_against_45000_at_2pct():
    # ₹45,000 invoice, ₹44,100 received = 2% TDS (standard rate, name-matched)
    proposals = propose_tds_matches([_txn(4_410_000)], [_inv()], PARTIES)
    assert len(proposals) == 1
    p = proposals[0]
    assert p["kind"] == "tds_adjusted"
    assert p["tds_paise"] == 90_000  # ₹900
    assert p["tds_bps"] == 200
    assert p["confidence"] == 0.80  # standard rate → below floor → approval queue
    assert p["amount_paise"] + p["tds_paise"] == 4_500_000


def test_remembered_rate_outranks_and_raises_confidence():
    remembered = {"p1": [200]}
    proposals = propose_tds_matches([_txn(4_410_000)], [_inv()], PARTIES, remembered)
    assert proposals[0]["confidence"] == 0.85  # memory-corroborated


def test_no_name_match_no_tds_guess():
    txn = _txn(4_410_000, hint=None, narration="IMPS TRANSFER CREDIT")
    assert propose_tds_matches([txn], [_inv()], PARTIES) == []


def test_non_tds_amount_not_matched():
    # ₹44,000 is not any standard-rate deduction of ₹45,000
    assert propose_tds_matches([_txn(4_400_000)], [_inv()], PARTIES) == []


def test_ambiguous_two_invoices_same_party_skipped():
    invoices = [_inv(id="i1"), _inv(id="i2")]  # both ₹45,000 → both 2% candidates
    assert propose_tds_matches([_txn(4_410_000)], invoices, PARTIES) == []


def test_critic_validates_tds_balance():
    proposals = propose_tds_matches([_txn(4_410_000)], [_inv()], PARTIES)
    ok = critic_review(proposals, [_inv()])
    assert ok[0]["critic_verdict"]["verdict"] == "pass"

    tampered = [{**proposals[0], "tds_paise": 1}]
    bad = critic_review(tampered, [_inv()])
    assert bad[0]["critic_verdict"]["verdict"] == "fail"


def test_parse_deduction_rates():
    contents = [
        "This client deducts 2% TDS on payments (seen on invoice INV-42).",
        "TDS of 10% applied on professional fees.",
        "Pays roughly 12 days late.",
    ]
    assert parse_deduction_rates(contents) == [200, 1000]
