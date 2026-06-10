"""Sandbox TReDS provider — deterministic quotes, local listing records.

Quotes are computed, not fetched: annualized DEFAULT_RATE_BPS over the tenor
(days until the seller expects the money anyway), so the cost is exactly what
you pay to move that arrival to today. Production swaps RXIL/M1xchange/
Invoicemart adapters behind the same surface; the token gate is identical.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from findesk_shared import uuid7

from findesk_tools.treds.schemas import ListingReceipt, ListingRefused, TredsQuote

DEFAULT_RATE_BPS = 1800  # 18% annualized — sandbox figure


class SandboxTredsProvider:
    name = "sandbox-treds"

    def __init__(self, listings_dir: str = "var/treds") -> None:
        self._dir = Path(listings_dir)

    def quote(
        self, *, invoice_ref: str, amount_paise: int, tenor_days: int
    ) -> TredsQuote:
        tenor_days = max(1, tenor_days)
        cost = round(amount_paise * DEFAULT_RATE_BPS / 10_000 * tenor_days / 365)
        return TredsQuote(
            invoice_ref=invoice_ref,
            platform=self.name,
            amount_paise=amount_paise,
            tenor_days=tenor_days,
            discount_rate_bps_annual=DEFAULT_RATE_BPS,
            cost_paise=cost,
            unlock_paise=amount_paise - cost,
            valid_until=datetime.now(UTC).date().isoformat(),
        )

    def list_invoice(
        self, *, tenant_id: str, quote: TredsQuote, approval_token: str | None
    ) -> ListingReceipt:
        if not approval_token:
            raise ListingRefused()
        listing_id = uuid7()
        folder = self._dir / tenant_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{listing_id}.json").write_text(
            json.dumps(
                {
                    "listing_id": listing_id,
                    "platform": self.name,
                    "listed_at": datetime.now(UTC).isoformat(),
                    "approval_token": approval_token,
                    "quote": quote.model_dump(),
                },
                indent=2,
            )
        )
        return ListingReceipt(
            listing_id=listing_id,
            platform=self.name,
            invoice_ref=quote.invoice_ref,
            unlock_paise=quote.unlock_paise,
            approval_token=approval_token,
        )
