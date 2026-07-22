"""tally@v1 schemas — mirrors contracts/tools.md exactly.

Sign convention: TallyPrime XML exports carry debit balances as negative
numbers. That convention is absorbed here — every amount leaving this layer is
a positive integer paise value, with meaning carried by the field name, never
by sign.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Source(BaseModel):
    kind: str = "tally"
    external_id: str
    fetched_at: datetime  # tz-aware UTC


class BillRef(BaseModel):
    """One outstanding bill row (receivable or payable — same shape)."""

    external_ref: str
    party: str
    bill_date: datetime  # tz-aware UTC (midnight IST converted)
    due_date: datetime | None = None
    amount_paise: int = Field(gt=0)
    outstanding_paise: int = Field(ge=0)
    source: Source


class Account(BaseModel):
    code: str  # Tally GUID when present, else name-derived ref
    name: str
    type: str  # Tally parent group verbatim, e.g. "Sundry Debtors"


class BillsResult(BaseModel):
    bills: list[BillRef]
    period: str  # "YYYY-MM-DD..YYYY-MM-DD"
    company: str | None = None


class ChartResult(BaseModel):
    accounts: list[Account]
    company: str | None = None


class LedgerEntry(BaseModel):
    ledger: str
    amount_paise: int = Field(gt=0)
    direction: str = Field(pattern="^(cr|dr)$")


class VoucherDraft(BaseModel):
    voucher_type: str  # e.g. "Journal", "Receipt"
    date: datetime
    narration: str
    ledger_entries: list[LedgerEntry] = Field(min_length=2)


class PushReceipt(BaseModel):
    external_id: str
    created: int
    altered: int
    approval_token: str  # echoed for the audit trail


class PushRefused(Exception):
    """Raised when push_voucher is attempted without a valid approval token.

    Writing to the books of record is consequential — no token, no voucher,
    no flag to disable (tools/CLAUDE.md rule 3).
    """

    def __init__(self) -> None:
        super().__init__("tally.push_voucher requires a single-use approval_token")


class ToolError(Exception):
    """contracts/tools.md error shape — graphs branch on retryable, not text."""

    def __init__(self, code: str, reason: str, *, retryable: bool = False) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.retryable = retryable
