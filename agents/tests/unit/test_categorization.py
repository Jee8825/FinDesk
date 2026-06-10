"""A3 categorization unit tests — pure logic."""

from findesk_agents.graphs.reconciliation.categorization import (
    categorize,
    parse_category_claims,
    rule_category,
    vendor_slug,
)

VALID = {"software_cloud", "payroll", "staff_welfare", "utilities", "taxes_gst"}


def _txn(id="t1", narration="AWS INDIA CLOUD SERVICES APR", hint=None, direction="dr", cat=None):
    return {
        "id": id,
        "direction": direction,
        "narration": narration,
        "counterparty_hint": hint,
        "category_code": cat,
    }


def test_rule_lexicon_hits():
    assert rule_category("AWS INDIA CLOUD SERVICES APR") == ("software_cloud", 0.92)
    assert rule_category("SALARY APR STAFF BATCH PAYOUT") == ("payroll", 0.95)
    assert rule_category("GST PAYMENT GSTR-3B MAR") == ("taxes_gst", 0.95)
    assert rule_category("UNKNOWN VENDOR XYZ") is None


def test_categorize_rule_path_and_skips():
    items = categorize([_txn(), _txn(id="t2", direction="cr")], {}, VALID)
    assert len(items) == 1
    assert items[0] == {
        "bank_transaction_id": "t1",
        "category_code": "software_cloud",
        "source": "rule",
        "confidence": 0.92,
        "vendor_slug": vendor_slug(_txn()),
        "vendor_label": "AWS INDIA CLOUD SERVICES APR"[:40],
    }


def test_memory_claim_outranks_rules_and_crystallization_boosts():
    txn = _txn(narration="UPI/zomato/LUNCH TEAM OFFSITE")
    slug = vendor_slug(txn)
    # ordinary claim
    items = categorize([txn], {slug: ("staff_welfare", 0.7)}, VALID)
    assert items[0]["source"] == "memory"
    assert items[0]["confidence"] == 0.85
    # crystallized claim
    items = categorize([txn], {slug: ("staff_welfare", 0.96)}, VALID)
    assert items[0]["confidence"] == 0.97


def test_invalid_memory_code_falls_back_to_rule():
    txn = _txn()
    slug = vendor_slug(txn)
    items = categorize([txn], {slug: ("nonexistent_code", 0.9)}, VALID)
    assert items[0]["source"] == "rule"


def test_already_categorized_untouched():
    assert categorize([_txn(cat="software_cloud")], {}, VALID) == []


def test_parse_category_claims_picks_highest_confidence():
    memories = [
        {"content": "Vendor 'X' expenses are categorized as payroll.", "confidence": 0.5},
        {
            "content": "Vendor 'X' expenses are categorized as staff_welfare "
            "(set by human correction).",
            "confidence": 0.9,
        },
        {"content": "irrelevant note", "confidence": 0.99},
    ]
    assert parse_category_claims(memories) == ("staff_welfare", 0.9)


def test_vendor_slug_stable():
    a = vendor_slug(_txn(hint="BLUE TOKAI COFFEE"))
    b = vendor_slug(_txn(hint="BLUE TOKAI COFFEE", narration="other"))
    assert a == b == "blue-tokai-coffee"
