"""IMS match core — deterministic tiers, tolerance boundary, totals rollup."""

from types import SimpleNamespace

from app.services.ims import TOLERANCE_PAISE, BillLite, classify, queue_totals

BILLS = [
    BillLite(
        number="PB-889",
        amount_paise=5_230_000,
        outstanding_paise=5_230_000,
        status="open",
        vendor="Sundaram Packaging (Udyam MSE)",
    ),
    BillLite(
        number="PB-901",
        amount_paise=78_000_000,
        outstanding_paise=78_000_000,
        status="open",
        vendor="Vega Logistics Pvt Ltd",
    ),
    BillLite(
        number="PB-870",
        amount_paise=6_400_000,
        outstanding_paise=0,
        status="paid",
        vendor="Sundaram Packaging (Udyam MSE)",
    ),
]
KNOWN = frozenset({"sundaram packaging (udyam mse)", "vega logistics pvt ltd"})


def _classify(**over):
    base = dict(
        doc_type="invoice",
        doc_number="PB-889",
        total_paise=5_230_000,
        tax_paise=797_797,
        supplier_name="Sundaram Packaging (Udyam MSE)",
        bills=BILLS,
        known_suppliers=KNOWN,
    )
    base.update(over)
    return classify(**base)


def test_exact_match_recommends_accept():
    v = _classify()
    assert (v.tier, v.recommendation, v.matched_bill_number) == ("exact", "accept", "PB-889")


def test_tolerant_within_max_of_rupee100_or_25bps():
    # PB-901 bill is ₹7,80,000; 25 bps = ₹1,950 > ₹100 → tolerance is 195_000 paise
    v = _classify(doc_number="PB-901", total_paise=78_000_000 + 195_000, tax_paise=1)
    assert (v.tier, v.recommendation) == ("tolerant", "accept")
    over = _classify(doc_number="PB-901", total_paise=78_000_000 + 195_001, tax_paise=1)
    assert (over.tier, over.recommendation) == ("amount_mismatch", "review")
    # small bill: absolute ₹100 floor governs
    v2 = _classify(total_paise=5_230_000 + TOLERANCE_PAISE)
    assert v2.tier == "tolerant"


def test_settled_bill_still_accepts_with_note():
    v = _classify(doc_number="PB-870", total_paise=6_400_000)
    assert (v.tier, v.recommendation) == ("exact", "accept")
    assert "settled" in v.note.lower()


def test_credit_note_always_reviews_with_itc_amount():
    v = _classify(doc_type="credit_note", doc_number="CN-12", tax_paise=305_085)
    assert (v.tier, v.recommendation) == ("credit_note", "review")
    assert "3,050.85" in v.note  # the ITC reversal spelled out


def test_known_supplier_without_bill_reviews_not_rejects():
    v = _classify(doc_number="VL-2209", supplier_name="Vega Logistics Pvt Ltd")
    assert (v.tier, v.recommendation) == ("no_bill", "review")


def test_unknown_supplier_flags_fraud_risk():
    v = _classify(doc_number="MT-4471", supplier_name="Meridian Traders")
    assert v.tier == "unknown_supplier"
    assert "reject" in v.note.lower()  # lean-reject guidance, human decides


def test_case_and_whitespace_insensitive_number_join():
    v = _classify(doc_number="  pb-889 ")
    assert v.tier == "exact"


def test_queue_totals_rollup():
    rows = [
        SimpleNamespace(state="pending", recommendation="accept", tax_paise=100),
        SimpleNamespace(state="pending", recommendation="review", tax_paise=250),
        SimpleNamespace(state="accepted", recommendation="accept", tax_paise=40),
        SimpleNamespace(state="rejected", recommendation="review", tax_paise=7),
    ]
    t = queue_totals(rows)
    assert t == {
        "pending_count": 2,
        "itc_at_stake_paise": 350,
        "review_count": 1,
        "accept_ready_paise": 100,
        "accepted_tax_paise": 40,
        "rejected_tax_paise": 7,
    }
