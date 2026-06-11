import pytest

from findesk_tools.bank_statements.schemas import ToolError
from findesk_tools.ledger_import import parse_invoice_export

ZOHO = (
    "Invoice Number,Invoice Date,Due Date,Customer Name,Total,Balance,"
    "Invoice Status,Payment Date\n"
    """INV-001,2026-01-10,2026-02-09,Phoenix Decor LLP,"1,18,000.00",0.00,Paid,2026-02-21
INV-002,2026-02-05,2026-03-07,Phoenix Decor LLP,"59,000.00",0.00,Paid,2026-03-19
INV-003,2026-05-20,2026-06-19,Phoenix Decor LLP,"2,36,000.00","2,36,000.00",Sent,
INV-004,2026-03-01,2026-03-31,Marigold Events,"45,000.00",0.00,Paid,2026-03-30
"""
)

TALLY = """Vch No,Vch Date,Party Name,Invoice Value,Outstanding
TLY-77,01-Apr-2026,Lotus Traders,90000.00,90000.00
TLY-78,05-Apr-2026,Lotus Traders,12000.00,0
"""


def test_zoho_export_parses_with_status_and_payment_dates():
    result = parse_invoice_export(ZOHO)
    assert result.source_hint == "zoho"
    assert len(result.invoices) == 4
    paid = [i for i in result.invoices if i.status == "paid"]
    assert len(paid) == 3
    inv1 = result.invoices[0]
    assert inv1.amount_paise == 11_800_000
    assert inv1.paid_date is not None and inv1.paid_date.day == 21  # 12 days late
    open_inv = result.invoices[2]
    assert open_inv.status == "open" and open_inv.paid_date is None


def test_tally_style_export_uses_outstanding_balance():
    result = parse_invoice_export(TALLY)
    assert result.source_hint == "tally"
    assert result.invoices[0].status == "open"
    assert result.invoices[1].status == "paid"
    assert result.invoices[0].due_date == result.invoices[0].issue_date  # no due column


def test_bad_header_raises():
    with pytest.raises(ToolError):
        parse_invoice_export("foo,bar\n1,2\n")
