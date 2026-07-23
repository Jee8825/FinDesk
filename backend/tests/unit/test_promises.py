"""Outcome loop core — PTP settlement boundary + write/parse twin round-trip."""

from datetime import date

from findesk_shared import late_phrase, parse_late_days

from app.services.promises import settle_outcome


def test_settle_outcome_boundary():
    promised = date(2026, 7, 20)
    assert settle_outcome(promised, date(2026, 7, 19)) == "kept"
    assert settle_outcome(promised, date(2026, 7, 20)) == "kept"  # on the day counts
    assert settle_outcome(promised, date(2026, 7, 21)) == "broken"


def test_late_phrase_round_trips_through_parser():
    # the settle path writes with late_phrase; the forecast reads with
    # parse_late_days — this is the drift guard between the twins
    assert parse_late_days([f"was paid {late_phrase(3)} relative to its due date"]) == [3]
    assert parse_late_days([f"was paid {late_phrase(-2)} …"]) == [-2]
    assert parse_late_days([f"was paid {late_phrase(0)} …"]) == [0]


def test_settlement_claim_sentence_parses():
    # exact sentence shape services/promises.py writes
    claim = (
        f"Invoice INV-042 was paid {late_phrase(7)} relative to its due date 2026-06-30."
    )
    assert parse_late_days([claim]) == [7]
