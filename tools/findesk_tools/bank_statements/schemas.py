"""bank_statements@v1 schemas — mirrors contracts/tools.md exactly."""

from __future__ import annotations

import hashlib
from datetime import datetime

from pydantic import BaseModel, Field


class NormalizedTxn(BaseModel):
    external_ref: str
    value_date: datetime  # tz-aware UTC
    amount_paise: int = Field(gt=0)
    direction: str = Field(pattern="^(cr|dr)$")
    narration: str
    counterparty_hint: str | None = None
    balance_paise: int | None = None

    def dedupe_hash(self) -> str:
        """Stable identity of a statement row across re-uploads."""
        key = "|".join(
            [
                self.external_ref,
                self.value_date.date().isoformat(),
                str(self.amount_paise),
                self.direction,
                self.narration.strip().lower(),
            ]
        )
        return hashlib.sha256(key.encode()).hexdigest()


class ParseResult(BaseModel):
    transactions: list[NormalizedTxn]
    bank: str
    account_ref: str
    period: str  # "YYYY-MM-DD..YYYY-MM-DD"
    skipped_rows: int = 0


class ToolError(Exception):
    def __init__(self, code: str, reason: str, *, retryable: bool = False) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.retryable = retryable
