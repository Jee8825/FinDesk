import uuid

from findesk_shared import format_inr, paise_to_rupees, uuid7


def test_uuid7_shape_and_version():
    u = uuid7()
    parsed = uuid.UUID(u)
    assert parsed.version == 7
    assert parsed.variant == uuid.RFC_4122


def test_uuid7_time_ordered():
    ids = [uuid7() for _ in range(500)]
    assert ids == sorted(ids)
    assert len(set(ids)) == 500


def test_format_inr_lakh_crore_grouping():
    assert format_inr(123456789) == "₹12,34,567.89"
    assert format_inr(4410000) == "₹44,100.00"
    assert format_inr(-150) == "-₹1.50"
    assert format_inr(99) == "₹0.99"
    # the spec's ₹8.1 trillion trapped-receivables number
    assert format_inr(810000000000000, symbol=False) == "81,00,00,00,00,000.00"


def test_paise_to_rupees_exact():
    assert str(paise_to_rupees(4410000)) == "44100"
