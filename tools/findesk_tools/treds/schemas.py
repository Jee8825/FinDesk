"""treds@v1 schemas — mirrors contracts/tools.md. list_invoice is ⚠ consequential."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TredsQuote(BaseModel):
    invoice_ref: str
    platform: str
    amount_paise: int = Field(gt=0)
    tenor_days: int = Field(ge=1)
    discount_rate_bps_annual: int  # annualized financing rate
    cost_paise: int  # discount charged for the tenor
    unlock_paise: int  # cash received now (amount − cost)
    valid_until: str


class ListingReceipt(BaseModel):
    listing_id: str
    platform: str
    invoice_ref: str
    unlock_paise: int
    approval_token: str  # echoed for the audit trail


class ListingRefused(Exception):
    """Raised when a listing is attempted without a valid approval token.

    Guardrail P2/P1 made physical: discounting a receivable changes who owns
    money — no token, no listing, no exceptions.
    """

    def __init__(self) -> None:
        super().__init__("treds.list_invoice requires a single-use approval_token")
