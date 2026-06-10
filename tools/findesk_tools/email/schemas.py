"""email@v1 schemas — mirrors contracts/tools.md. Send is ⚠ consequential."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class EmailDraft(BaseModel):
    to: list[EmailStr]
    subject: str = Field(max_length=200)
    body_md: str = Field(max_length=8000)
    thread_ref: str | None = None  # e.g. invoice:<id> — groups follow-ups


class SendReceipt(BaseModel):
    message_id: str
    provider: str
    approval_token: str  # echoed for the audit trail


class SendRefused(Exception):
    """Raised when a send is attempted without a valid approval token.

    Guardrail P2 made physical: the tool has no unsanctioned send path —
    a compromised prompt cannot email anyone.
    """

    def __init__(self) -> None:
        super().__init__("email.send requires a single-use approval_token (guardrail P2)")
