"""CSV statement parser (bank_statements@v1).

Phase 1 supports the generic Indian-bank CSV layout used by our fixtures and
most net-banking exports:

    Date,Narration,Ref No,Debit,Credit,Balance

- Date: DD/MM/YYYY or YYYY-MM-DD
- Debit/Credit: rupees with optional commas/₹; exactly one of the two per row
- Amounts parsed to integer paise (never floats)

Per-bank quirk adapters (ICICI/HDFC/SBI header variants) register in
_HEADER_ALIASES as they show up in real exports.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from findesk_tools.bank_statements.schemas import NormalizedTxn, ParseResult, ToolError

_HEADER_ALIASES = {
    "date": {"date", "txn date", "transaction date", "value date", "value dt"},
    "narration": {"narration", "description", "particulars", "remarks", "transaction remarks"},
    "ref": {"ref no", "ref", "reference", "cheque/ref no", "chq/ref no", "utr", "tran id"},
    "debit": {"debit", "withdrawal", "withdrawal amt", "withdrawal amt (inr)", "dr"},
    "credit": {"credit", "deposit", "deposit amt", "deposit amt (inr)", "cr"},
    "balance": {"balance", "closing balance", "balance (inr)"},
}

_HINT_PATTERNS = [
    # optional middle token = lowercase rail handles only (UPI/payu/…), so an
    # uppercase counterparty name is never swallowed (NEFT-BLUE TOKAI…)
    re.compile(r"(?:NEFT|RTGS|IMPS|UPI)[-/ ](?:[a-z0-9]+[-/ ])?([A-Za-z][A-Za-z &.]{3,40})"),
    re.compile(r"(?:FROM|BY|TRF FROM)\s+([A-Za-z][A-Za-z &.]{3,40})", re.IGNORECASE),
]


def _canon_header(raw: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(raw):
        cell_norm = cell.strip().lower()
        for canon, aliases in _HEADER_ALIASES.items():
            if cell_norm in aliases and canon not in mapping:
                mapping[canon] = idx
    return mapping


def _parse_date(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ToolError("bad_date", f"unparseable date {value!r}")


def _parse_paise(value: str) -> int | None:
    cleaned = value.strip().replace(",", "").replace("₹", "").replace("INR", "").strip()
    if not cleaned or cleaned in {"-", "0", "0.0", "0.00"}:
        return None
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ToolError("bad_amount", f"unparseable amount {value!r}") from exc
    paise = int((amount * 100).to_integral_value())
    return paise if paise > 0 else None


def counterparty_hint(narration: str) -> str | None:
    for pattern in _HINT_PATTERNS:
        m = pattern.search(narration)
        if m:
            hint = re.sub(r"\s+", " ", m.group(1)).strip(" .-")
            if len(hint) >= 3:
                return hint
    return None


def parse_statement(
    content: str, *, bank: str = "unknown", account_ref: str = "uploaded"
) -> ParseResult:
    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ToolError("empty", "no rows in statement")

    header = _canon_header(rows[0])
    required = {"date", "narration", "debit", "credit"}
    if not required.issubset(header):
        missing = required - set(header)
        raise ToolError("bad_header", f"unrecognized statement header; missing {sorted(missing)}")

    txns: list[NormalizedTxn] = []
    skipped = 0
    for line_no, row in enumerate(rows[1:], start=2):
        try:
            debit = _parse_paise(row[header["debit"]]) if header["debit"] < len(row) else None
            credit = _parse_paise(row[header["credit"]]) if header["credit"] < len(row) else None
            if debit is None and credit is None:
                skipped += 1
                continue
            narration = row[header["narration"]].strip()
            balance = (
                _parse_paise(row[header["balance"]])
                if "balance" in header and header["balance"] < len(row)
                else None
            )
            txns.append(
                NormalizedTxn(
                    external_ref=(
                        row[header["ref"]].strip()
                        if "ref" in header
                        and header["ref"] < len(row)
                        and row[header["ref"]].strip()
                        else f"row-{line_no}"
                    ),
                    value_date=_parse_date(row[header["date"]]),
                    amount_paise=credit if credit is not None else debit,  # type: ignore[arg-type]
                    direction="cr" if credit is not None else "dr",
                    narration=narration,
                    counterparty_hint=counterparty_hint(narration),
                    balance_paise=balance,
                )
            )
        except ToolError:
            skipped += 1

    if not txns:
        raise ToolError("no_transactions", "statement parsed but no valid transactions found")

    dates = sorted(t.value_date.date() for t in txns)
    return ParseResult(
        transactions=txns,
        bank=bank,
        account_ref=account_ref,
        period=f"{dates[0].isoformat()}..{dates[-1].isoformat()}",
        skipped_rows=skipped,
    )
