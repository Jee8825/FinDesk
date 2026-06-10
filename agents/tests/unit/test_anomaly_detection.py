"""A6 detection unit tests — pure logic."""

from findesk_agents.graphs.anomaly_scan.detection import (
    baseline_claims,
    detect_deviations,
    detect_duplicates,
)


def _txn(id, amount, narration="WEWORK BKC RENT", date="2026-04-09", hint=None):
    return {
        "id": id,
        "value_date": f"{date}T00:00:00+00:00",
        "amount_paise": amount,
        "narration": narration,
        "counterparty_hint": hint,
    }


def test_duplicate_within_window_flagged_with_recoverable():
    txns = [
        _txn("t1", 8_500_000, date="2026-04-09"),
        _txn("t2", 8_500_000, date="2026-04-11"),
    ]
    findings = detect_duplicates(txns)
    assert len(findings) == 1
    f = findings[0]
    assert f["kind"] == "duplicate"
    assert f["recoverable_paise"] == 8_500_000
    assert f["evidence"]["days_apart"] == 2


def test_same_amount_far_apart_is_recurring_not_duplicate():
    txns = [
        _txn("t1", 8_500_000, date="2026-04-09"),
        _txn("t2", 8_500_000, date="2026-05-09"),
    ]
    assert detect_duplicates(txns) == []


def test_overcharge_against_stable_baseline():
    txns = [
        _txn("a1", 680_000, narration="AWS INDIA CLOUD APR", date="2026-04-07"),
        _txn("a2", 680_000, narration="AWS INDIA CLOUD APR", date="2026-05-05"),
        _txn("a3", 1_940_000, narration="AWS INDIA CLOUD APR", date="2026-06-05"),
    ]
    findings = detect_deviations(txns)
    assert len(findings) == 1
    f = findings[0]
    assert f["kind"] == "overcharge"
    assert f["recoverable_paise"] == 1_940_000 - 680_000
    assert f["evidence"]["ratio"] >= 2.8


def test_memory_baseline_enables_detection_with_thin_history():
    # only one in-window txn, but memory remembers the usual bill
    txns = [_txn("a1", 1_940_000, narration="AWS INDIA CLOUD JUN", date="2026-06-05")]
    vendor = "aws-india-cloud"  # month tokens stripped by the shared slug
    findings = detect_deviations(txns, {vendor: [680_000, 680_000]})
    assert len(findings) == 1
    assert findings[0]["kind"] == "overcharge"


def test_mild_deviation_is_out_of_pattern_not_overcharge():
    txns = [
        _txn("a1", 680_000, date="2026-04-07"),
        _txn("a2", 680_000, date="2026-05-05"),
        _txn("a3", 920_000, date="2026-06-05"),  # 1.35×
    ]
    findings = detect_deviations(txns)
    assert findings[0]["kind"] == "out_of_pattern"
    assert findings[0]["recoverable_paise"] is None


def test_unstable_history_produces_no_baseline():
    txns = [
        _txn("a1", 100_000, date="2026-04-07"),
        _txn("a2", 900_000, date="2026-05-05"),
        _txn("a3", 2_000_000, date="2026-06-05"),
    ]
    assert detect_deviations(txns) == []
    assert baseline_claims(txns) == {}


def test_baseline_claims_for_stable_vendors():
    txns = [
        _txn("a1", 680_000, date="2026-04-07"),
        _txn("a2", 680_000, date="2026-05-05"),
    ]
    claims = baseline_claims(txns)
    assert list(claims.values()) == [680_000]
