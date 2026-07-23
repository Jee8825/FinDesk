"""udyam@v1 schemas — mirrors contracts/tools.md. Read-only verification.

Verification is a lookup, not an action — no approval token involved. What
makes it load-bearing: §15/§16 clocks and 43B(h) exposure scope on the
*verified* category when one exists, because MSE status changes year to year
and a self-declared tag protects against the wrong list.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UdyamCategory = Literal["micro", "small", "medium"]


class UdyamVerification(BaseModel):
    urn: str = Field(min_length=16, max_length=25)  # UDYAM-XX-00-0000000
    found: bool
    enterprise_name: str | None = None
    category: UdyamCategory | None = None
    major_activity: str | None = None
    as_of: str | None = None  # date the register reflected this
