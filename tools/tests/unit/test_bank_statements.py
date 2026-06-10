import pytest

from findesk_tools.bank_statements import ToolError, parse_statement

FIXTURE = """Date,Narration,Ref No,Debit,Credit,Balance
01/04/2026,NEFT-BLUE TOKAI COFFEE-INV0042,N1001,,"45,000.00","5,45,000.00"
02/04/2026,UPI/payu/ZOMATO LTD lunch,U2002,1250.50,,"5,43,749.50"
03/04/2026,IMPS-ORIGIN ROASTERS PVT LTD-PAY,I3003,,"1,18,000.00","6,61,749.50"
04/04/2026,SALARY APR STAFF BATCH,S4004,"3,20,000.00",,"3,41,749.50"
05/04/2026,,X5005,,,
"""


def test_parse_basic_statement():
    result = parse_statement(FIXTURE, bank="demo", account_ref="XX1234")
    assert len(result.transactions) == 4
    assert result.skipped_rows == 1
    assert result.period == "2026-04-01..2026-04-04"

    t0 = result.transactions[0]
    assert t0.amount_paise == 4_500_000  # ₹45,000 in paise
    assert t0.direction == "cr"
    assert t0.counterparty_hint and "BLUE TOKAI" in t0.counterparty_hint.upper()
    assert t0.balance_paise == 54_500_000

    t1 = result.transactions[1]
    assert t1.direction == "dr"
    assert t1.amount_paise == 125_050  # paise math, no float drift


def test_dedupe_hash_stable_and_distinct():
    result = parse_statement(FIXTURE)
    again = parse_statement(FIXTURE)
    h1 = [t.dedupe_hash() for t in result.transactions]
    h2 = [t.dedupe_hash() for t in again.transactions]
    assert h1 == h2
    assert len(set(h1)) == len(h1)


def test_alias_headers_and_iso_dates():
    csv_text = (
        "Value Date,Particulars,UTR,Withdrawal Amt,Deposit Amt,Closing Balance\n"
        "2026-04-07,RTGS-ACME CORP-ADV,R1,,99.99,100.00\n"
    )
    result = parse_statement(csv_text)
    assert result.transactions[0].amount_paise == 9999
    assert result.transactions[0].value_date.year == 2026


def test_bad_header_raises_tool_error():
    with pytest.raises(ToolError) as exc:
        parse_statement("foo,bar\n1,2\n")
    assert exc.value.code == "bad_header"


def test_empty_raises():
    with pytest.raises(ToolError):
        parse_statement("   \n  ")
