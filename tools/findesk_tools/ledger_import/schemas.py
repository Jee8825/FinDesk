"""ledger_import@v1 schemas — Tally/Zoho invoice exports normalized."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ImportedInvoice(BaseModel):
    number: str
    client_name: str
    issue_date: datetime
    due_date: datetime
    amount_paise: int = Field(gt=0)
    status: str = Field(pattern="^(open|paid)$")
    paid_date: datetime | None = None  # drives historical behavior seeding


class ImportResult(BaseModel):
    invoices: list[ImportedInvoice]
    source_hint: str  # zoho | tally | generic
    skipped_rows: int = 0
