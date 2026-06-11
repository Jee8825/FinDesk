"""Invoice-export parser (ledger_import@v1) — Zoho Books / Tally CSV exports.

Both systems export invoice registers as CSV with vendor-specific headers;
the alias table normalizes them the same way bank_statements handles bank
header quirks. Native Tally XML lands later behind the same surface.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from findesk_tools.bank_statements.schemas import ToolError
from findesk_tools.ledger_import.schemas import ImportedInvoice, ImportResult

_ALIASES = {
    "number": {"invoice number", "invoice no", "invoice#", "voucher no", "vch no", "bill no"},
    "client": {"customer name", "party name", "client", "buyer", "party"},
    "issue_date": {"invoice date", "date", "voucher date", "vch date"},
    "due_date": {"due date", "payment due", "credit due date"},
    "amount": {"total", "invoice amount", "amount", "gross total", "invoice value"},
    "balance": {"balance", "balance due", "outstanding", "pending amount"},
    "status": {"invoice status", "status"},
    "paid_date": {"payment date", "last payment date", "receipt date"},
}

_PAID_WORDS = {"paid", "closed", "settled"}


def _canon_header(raw: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(raw):
        cell_norm = cell.strip().lower().lstrip("﻿")
        for canon, aliases in _ALIASES.items():
            if cell_norm in aliases and canon not in mapping:
                mapping[canon] = idx
    return mapping


def _date(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ToolError("bad_date", f"unparseable date {value!r}")


def _paise(value: str) -> int:
    cleaned = value.strip().replace(",", "").replace("₹", "").replace("INR", "").strip()
    try:
        return int((Decimal(cleaned or "0") * 100).to_integral_value())
    except InvalidOperation as exc:
        raise ToolError("bad_amount", f"unparseable amount {value!r}") from exc


def _cell(row: list[str], header: dict[str, int], key: str) -> str:
    idx = header.get(key)
    return row[idx].strip() if idx is not None and idx < len(row) else ""


def parse_invoice_export(content: str) -> ImportResult:
    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ToolError("empty", "no rows in export")
    header = _canon_header(rows[0])
    required = {"number", "client", "issue_date", "amount"}
    if not required.issubset(header):
        raise ToolError(
            "bad_header", f"unrecognized export header; missing {sorted(required - set(header))}"
        )
    source_hint = (
        "zoho"
        if "invoice status" in [c.strip().lower() for c in rows[0]]
        else "tally"
        if any(c.strip().lower().startswith("vch") for c in rows[0])
        else "generic"
    )

    invoices: list[ImportedInvoice] = []
    skipped = 0
    for row in rows[1:]:
        try:
            amount = _paise(_cell(row, header, "amount"))
            if amount <= 0:
                skipped += 1
                continue
            issue = _date(_cell(row, header, "issue_date"))
            due_raw = _cell(row, header, "due_date")
            due = _date(due_raw) if due_raw else issue
            status_raw = _cell(row, header, "status").lower()
            balance_raw = _cell(row, header, "balance")
            paid = (
                status_raw in _PAID_WORDS
                if status_raw
                else (balance_raw != "" and _paise(balance_raw) == 0)
            )
            paid_date_raw = _cell(row, header, "paid_date")
            invoices.append(
                ImportedInvoice(
                    number=_cell(row, header, "number"),
                    client_name=_cell(row, header, "client"),
                    issue_date=issue,
                    due_date=due,
                    amount_paise=amount,
                    status="paid" if paid else "open",
                    paid_date=_date(paid_date_raw) if paid_date_raw and paid else None,
                )
            )
        except ToolError:
            skipped += 1
    if not invoices:
        raise ToolError("no_invoices", "export parsed but no valid invoices found")
    return ImportResult(invoices=invoices, source_hint=source_hint, skipped_rows=skipped)
