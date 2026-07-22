"""Tally gateway tests — envelope building, flat-sibling parsing, the push gate."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from findesk_tools.tally import (
    LedgerEntry,
    PushRefused,
    TallyGateway,
    ToolError,
    VoucherDraft,
)
from findesk_tools.tally.envelopes import parse_tally_date, rupees_to_paise_abs

FIXTURES = Path(__file__).resolve().parents[2] / "findesk_tools" / "tally" / "fixtures"


def fixture_transport(name: str, captured: list[str] | None = None):
    def transport(url: str, request_xml: str) -> str:
        if captured is not None:
            captured.append(request_xml)
        return (FIXTURES / name).read_text(encoding="utf-8")

    return transport


# ------------------------------------------------------------------ parsing --

def test_bills_receivable_flat_siblings_grouped():
    gw = TallyGateway(transport=fixture_transport("bills_receivable.xml"))
    result = gw.list_invoices("2026-04-01", "2026-07-22")
    assert len(result.bills) == 3
    first = result.bills[0]
    assert first.external_ref == "INV-2026-041"
    assert first.party == "Meridian Fabrics Pvt Ltd"
    # debit-negative rupees normalized to positive paise
    assert first.outstanding_paise == 11_800_000
    assert first.amount_paise == 11_800_000  # no BILLOP → outstanding stands in
    assert first.due_date == datetime(2026, 5, 16, tzinfo=UTC)


def test_partially_settled_bill_keeps_opening_amount():
    gw = TallyGateway(transport=fixture_transport("bills_receivable.xml"))
    partial = gw.list_invoices("2026-04-01", "2026-07-22").bills[1]
    assert partial.amount_paise == 23_650_050  # BILLOP
    assert partial.outstanding_paise == 9_650_050  # BILLCL


def test_blank_billref_gets_stable_fallback_and_numeric_date_parses():
    gw = TallyGateway(transport=fixture_transport("bills_receivable.xml"))
    last = gw.list_invoices("2026-04-01", "2026-07-22").bills[2]
    assert last.external_ref.startswith("tally:Kubera Traders:")
    assert last.bill_date == datetime(2026, 6, 10, tzinfo=UTC)
    assert last.due_date is None


def test_bills_payable_uses_payable_report_and_parses():
    captured: list[str] = []
    gw = TallyGateway(transport=fixture_transport("bills_payable.xml", captured))
    result = gw.list_bills("2026-04-01", "2026-07-22")
    assert "<ID>Bills Payable</ID>" in captured[0]
    assert "<SVFROMDATE>20260401</SVFROMDATE>" in captured[0]
    assert [b.party for b in result.bills] == [
        "Sundaram Packaging (Udyam MSE)",
        "Vega Logistics Pvt Ltd",
    ]
    assert result.bills[0].outstanding_paise == 5_230_000


def test_chart_of_accounts_guid_and_name_fallback():
    gw = TallyGateway(transport=fixture_transport("ledgers.xml"))
    accounts = gw.get_chart_of_accounts().accounts
    assert len(accounts) == 3
    assert accounts[0].code.startswith("9a1f6c2e")
    assert accounts[0].type == "Sundry Debtors"
    assert accounts[2].code == "name:HDFC Bank CA 2201"  # blank GUID → name ref


def test_line_error_maps_to_tool_error():
    gw = TallyGateway(transport=fixture_transport("line_error.xml"))
    with pytest.raises(ToolError) as err:
        gw.list_invoices("2026-04-01", "2026-07-22")
    assert err.value.code == "tally.line_error"
    assert not err.value.retryable


# --------------------------------------------------------------- push gate --

def _draft() -> VoucherDraft:
    return VoucherDraft(
        voucher_type="Journal",
        date=datetime(2026, 7, 1, tzinfo=UTC),
        narration="FinDesk recon adjustment",
        ledger_entries=[
            LedgerEntry(ledger="Bank Charges", amount_paise=45_000, direction="dr"),
            LedgerEntry(ledger="HDFC Bank CA 2201", amount_paise=45_000, direction="cr"),
        ],
    )


def test_push_refused_without_token_and_no_gateway_call():
    calls: list[str] = []
    gw = TallyGateway(transport=fixture_transport("import_ok.xml", calls))
    with pytest.raises(PushRefused):
        gw.push_voucher(_draft(), approval_token=None)
    assert calls == []  # refusal happens before any I/O


def test_push_with_token_builds_signed_amounts_and_parses_receipt():
    calls: list[str] = []
    gw = TallyGateway(transport=fixture_transport("import_ok.xml", calls))
    receipt = gw.push_voucher(_draft(), approval_token="tok-7")
    assert receipt.external_id == "10245"
    assert receipt.created == 1
    assert receipt.approval_token == "tok-7"
    body = calls[0]
    assert "<AMOUNT>-450.00</AMOUNT>" in body  # debit negative (Tally convention)
    assert "<AMOUNT>450.00</AMOUNT>" in body  # credit positive
    assert "<DATE>20260701</DATE>" in body


# ------------------------------------------------------------------ helpers --

def test_date_and_amount_edge_parsing():
    assert parse_tally_date("1-Apr-2026") == datetime(2026, 4, 1, tzinfo=UTC)
    assert parse_tally_date("20260401") == datetime(2026, 4, 1, tzinfo=UTC)
    assert rupees_to_paise_abs("-1,18,000.00") == 11_800_000
    with pytest.raises(ToolError):
        parse_tally_date("Aprilish")
    with pytest.raises(ToolError):
        rupees_to_paise_abs("abc")
