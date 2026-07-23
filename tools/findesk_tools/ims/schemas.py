"""ims@v1 schemas — mirrors contracts/tools.md. set_state is ⚠ consequential.

An ImsRecord is a supplier-reported document sitting in the tenant's GST
Invoice Management System queue: what the supplier filed in GSTR-1/1A/IFF.
Accept/reject/pending decides the tenant's own ITC — so state changes only
execute behind an approval token, exactly like email sends and TReDS listings.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DocType = Literal["invoice", "credit_note", "debit_note"]
ImsState = Literal["pending", "accepted", "rejected"]


class ImsRecord(BaseModel):
    supplier_gstin: str = Field(min_length=15, max_length=15)
    supplier_name: str
    doc_type: DocType = "invoice"
    doc_number: str
    doc_date: str  # ISO date as filed
    period: str  # return period the record landed in, e.g. "2026-07"
    taxable_value_paise: int = Field(ge=0)
    tax_paise: int = Field(ge=0)  # IGST+CGST+SGST combined — the ITC at stake
    total_paise: int = Field(gt=0)
    state: ImsState = "pending"

    @property
    def key(self) -> str:
        """Stable identity of a filed document across re-pulls."""
        return f"{self.supplier_gstin}:{self.doc_type}:{self.doc_number}"


class ImsActionReceipt(BaseModel):
    action_id: str
    record_key: str
    state: ImsState
    acted_at: str
    approval_token: str  # echoed for the audit trail


class ImsActionRefused(Exception):
    """Raised when set_state is attempted without a valid approval token.

    Accepting a record claims input-tax credit on the tenant's GSTR-3B;
    rejecting one pushes the document back to the supplier. Both are
    consequential filings-adjacent actions — the token gate is physical,
    not prompt text, in every environment.
    """
