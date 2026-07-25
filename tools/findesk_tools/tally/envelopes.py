"""TallyPrime HTTP-XML gateway envelopes — build requests, parse responses.

Pure functions, no I/O. The gateway protocol (TallyPrime, Gateway of Tally →
listens on :9000 by default):

* Requests are ``<ENVELOPE><HEADER>…</HEADER><BODY>…</BODY></ENVELOPE>`` posted
  as the raw request body.
* Bills Receivable / Bills Payable are Report exports (``TYPE=Data``); the
  response DATA section is the notorious *flat sibling* structure — repeated
  ``BILLFIXED`` / ``BILLCL`` / ``BILLDUE`` elements in document order, NOT
  wrapped per bill. We group by walking siblings until the next BILLFIXED.
* Ledger masters come back as ``<LEDGER NAME="…">`` elements with PARENT /
  GUID / CLOSINGBALANCE children.
* Amounts are rupees with Tally's debit-negative sign convention; dates are
  ``1-Apr-2026`` or ``20260401``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from findesk_tools.tally.schemas import Account, ToolError

_TALLY_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# ---------------------------------------------------------------- requests --

def _static_vars(company: str | None, extra: dict[str, str] | None = None) -> str:
    parts = ["<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"]
    if company:
        parts.append(f"<SVCURRENTCOMPANY>{_escape(company)}</SVCURRENTCOMPANY>")
    for tag, value in (extra or {}).items():
        parts.append(f"<{tag}>{_escape(value)}</{tag}>")
    return "".join(parts)


def _export_report(report: str, company: str | None, extra: dict[str, str] | None = None) -> str:
    return (
        "<ENVELOPE><HEADER><VERSION>1</VERSION>"
        "<TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE>"
        f"<ID>{report}</ID></HEADER><BODY><DESC><STATICVARIABLES>"
        f"{_static_vars(company, extra)}"
        "</STATICVARIABLES></DESC></BODY></ENVELOPE>"
    )


def bills_receivable_request(from_date: str, to_date: str, company: str | None = None) -> str:
    """from/to are Tally-format dates ``YYYYMMDD``."""
    return _export_report(
        "Bills Receivable", company, {"SVFROMDATE": from_date, "SVTODATE": to_date}
    )


def bills_payable_request(from_date: str, to_date: str, company: str | None = None) -> str:
    return _export_report(
        "Bills Payable", company, {"SVFROMDATE": from_date, "SVTODATE": to_date}
    )


def ledgers_request(company: str | None = None) -> str:
    """Collection export of ledger masters via an inline TDL collection."""
    return (
        "<ENVELOPE><HEADER><VERSION>1</VERSION>"
        "<TALLYREQUEST>Export</TALLYREQUEST><TYPE>COLLECTION</TYPE>"
        "<ID>FinDesk Ledgers</ID></HEADER><BODY><DESC><STATICVARIABLES>"
        f"{_static_vars(company)}"
        "</STATICVARIABLES><TDL><TDLMESSAGE>"
        '<COLLECTION NAME="FinDesk Ledgers" ISMODIFY="No">'
        "<TYPE>Ledger</TYPE><FETCH>NAME,PARENT,GUID,CLOSINGBALANCE</FETCH>"
        "</COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"
    )


def import_voucher_request(
    *,
    voucher_type: str,
    date: str,  # YYYYMMDD
    narration: str,
    entries: list[tuple[str, Decimal, str]],  # (ledger, rupees, cr|dr)
    company: str | None = None,
) -> str:
    """Import Data envelope creating one voucher.

    Tally convention: ledger AMOUNT is negative for debit, positive for credit;
    ISDEEMEDPOSITIVE mirrors the debit flag.
    """
    lines = []
    for ledger, rupees, direction in entries:
        signed = -rupees if direction == "dr" else rupees
        deemed = "Yes" if direction == "dr" else "No"
        lines.append(
            "<ALLLEDGERENTRIES.LIST>"
            f"<LEDGERNAME>{_escape(ledger)}</LEDGERNAME>"
            f"<ISDEEMEDPOSITIVE>{deemed}</ISDEEMEDPOSITIVE>"
            f"<AMOUNT>{signed:.2f}</AMOUNT>"
            "</ALLLEDGERENTRIES.LIST>"
        )
    return (
        "<ENVELOPE><HEADER><VERSION>1</VERSION>"
        "<TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE>"
        "<ID>Vouchers</ID></HEADER><BODY><DESC><STATICVARIABLES>"
        f"{_static_vars(company)}"
        "</STATICVARIABLES></DESC><DATA><TALLYMESSAGE>"
        f'<VOUCHER VCHTYPE="{_escape(voucher_type)}" ACTION="Create">'
        f"<DATE>{date}</DATE>"
        f"<VOUCHERTYPENAME>{_escape(voucher_type)}</VOUCHERTYPENAME>"
        f"<NARRATION>{_escape(narration)}</NARRATION>"
        f"{''.join(lines)}"
        "</VOUCHER></TALLYMESSAGE></DATA></BODY></ENVELOPE>"
    )


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


# --------------------------------------------------------------- responses --

def parse_tally_date(raw: str) -> datetime:
    """``1-Apr-2026`` or ``20260401`` → tz-aware UTC midnight."""
    text = raw.strip()
    try:
        if "-" in text:
            day, mon, year = text.split("-")
            month = _TALLY_MONTHS[mon[:3].lower()]
            return datetime(int(year), month, int(day), tzinfo=UTC)
        return datetime(int(text[:4]), int(text[4:6]), int(text[6:8]), tzinfo=UTC)
    except (ValueError, KeyError, IndexError) as exc:
        raise ToolError("tally.bad_date", f"unparseable Tally date: {raw!r}") from exc


def rupees_to_paise_abs(raw: str) -> int:
    """Rupee string (possibly debit-negative) → positive integer paise."""
    try:
        return abs(int((Decimal(raw.strip().replace(",", "")) * 100).to_integral_value()))
    except (InvalidOperation, ValueError) as exc:
        raise ToolError("tally.bad_amount", f"unparseable Tally amount: {raw!r}") from exc


def _root(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ToolError("tally.bad_xml", f"gateway returned invalid XML: {exc}") from exc


def check_response_errors(xml_text: str) -> ET.Element:
    """Parse an envelope, raising ToolError on LINEERROR / non-1 STATUS."""
    root = _root(xml_text)
    line_error = root.find(".//LINEERROR")
    if line_error is not None and (line_error.text or "").strip():
        raise ToolError("tally.line_error", line_error.text.strip())  # type: ignore[union-attr]
    status = root.find("./HEADER/STATUS")
    if status is not None and (status.text or "").strip() not in {"", "1"}:
        raise ToolError("tally.bad_status", f"gateway status {status.text}", retryable=True)
    return root


def parse_bills(xml_text: str, *, fetched_at: datetime) -> list[dict]:
    """Flat-sibling BILLFIXED/BILLCL/BILLDUE walk → row dicts (see module doc)."""
    root = check_response_errors(xml_text)
    rows: list[dict] = []
    current: dict | None = None
    for el in root.iter():
        if el.tag == "BILLFIXED":
            if current is not None:
                rows.append(current)
            current = {
                "external_ref": (el.findtext("BILLREF") or "").strip(),
                "party": (el.findtext("BILLPARTY") or "").strip(),
                "bill_date_raw": (el.findtext("BILLDATE") or "").strip(),
                "fetched_at": fetched_at,
            }
        elif current is not None and el.tag == "BILLCL":
            current["outstanding_raw"] = (el.text or "0").strip()
        elif current is not None and el.tag == "BILLOP":
            current["amount_raw"] = (el.text or "0").strip()
        elif current is not None and el.tag == "BILLDUE":
            current["due_date_raw"] = (el.text or "").strip()
    if current is not None:
        rows.append(current)
    return rows


def parse_ledgers(xml_text: str) -> list[Account]:
    root = check_response_errors(xml_text)
    accounts: list[Account] = []
    for el in root.iter("LEDGER"):
        name = (el.get("NAME") or el.findtext("NAME") or "").strip()
        if not name:
            continue
        guid = (el.findtext("GUID") or "").strip()
        accounts.append(
            Account(
                code=guid or f"name:{name}",
                name=name,
                type=(el.findtext("PARENT") or "").strip(),
            )
        )
    return accounts


def parse_import_response(xml_text: str) -> dict:
    root = check_response_errors(xml_text)
    created = int((root.findtext(".//CREATED") or "0").strip() or 0)
    altered = int((root.findtext(".//ALTERED") or "0").strip() or 0)
    vch_id = (root.findtext(".//LASTVCHID") or "").strip()
    if created == 0 and altered == 0:
        raise ToolError("tally.import_rejected", "gateway accepted no vouchers")
    return {"created": created, "altered": altered, "external_id": vch_id or "unknown"}
