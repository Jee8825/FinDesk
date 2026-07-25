"""Demo transport — serves the checked-in gateway fixtures without a TallyPrime.

Lets the product exercise the *real* connector code path (envelopes → parser →
normalization) when no gateway is reachable. Every consumer that uses this
transport must label its output as fixture-sourced — never present demo data
as a live pull.
"""

from __future__ import annotations

from pathlib import Path

_FIXTURES = Path(__file__).resolve().parent / "fixtures"

_BY_REPORT = {
    "Bills Receivable": "bills_receivable.xml",
    "Bills Payable": "bills_payable.xml",
    "FinDesk Ledgers": "ledgers.xml",
    "Vouchers": "import_ok.xml",
}


def fixture_transport(url: str, request_xml: str) -> str:
    for report, filename in _BY_REPORT.items():
        if f"<ID>{report}</ID>" in request_xml:
            return (_FIXTURES / filename).read_text(encoding="utf-8")
    raise AssertionError("no fixture for request")  # pragma: no cover
