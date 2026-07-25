"""Parse Indian bank debit-alert SMS into transaction rows.

Templates vary by bank but share a skeleton: an amount, a direction word, an
account fragment, a date, and a merchant tail. We match the skeleton rather than
whole messages, so a bank tweaking its wording does not silently drop every alert.

Credit alerts, OTPs, balance summaries and promotional texts are ignored — a
leak detector only cares about money leaving. Nothing here is money-moving; it is
read-only text parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

# ₹1,234.00 / Rs.1234 / INR 1,234.56
_AMOUNT = r"(?:rs\.?|inr|₹)\s?([\d,]+(?:\.\d{1,2})?)"
_DEBIT_WORDS = r"(?:debited|debit|spent|paid|withdrawn|deducted)"
_CREDIT_WORDS = r"(?:credited|credit|received|refund)"

_DATE_PATTERNS = (
    (re.compile(r"(\d{2})-(\d{2})-(\d{2,4})"), "%d-%m-%Y"),
    (re.compile(r"(\d{2})/(\d{2})/(\d{2,4})"), "%d/%m/%Y"),
    (re.compile(r"(\d{2})-([A-Za-z]{3})-(\d{2,4})"), "%d-%b-%Y"),
)

# merchant tail: "to NETFLIX", "at SWIGGY", "towards ADOBE", "for AWS INDIA"
_MERCHANT = re.compile(
    r"\b(?:to|at|towards|for|info:?)\s+([A-Za-z][A-Za-z0-9 &._-]{2,40})",
    re.IGNORECASE,
)
_ACCOUNT = re.compile(r"(?:a/c|acct|account|ac)\s*(?:no\.?)?\s*[xX*]*(\d{3,4})", re.IGNORECASE)

_NOISE_TAIL = re.compile(r"\b(?:not you|call|sms|block|dispute|ref|upi|txn|avl|bal).*", re.I)


@dataclass
class ParsedSms:
    value_date: datetime
    amount_paise: int
    narration: str
    account_ref: str | None
    bank: str | None

    def as_row(self) -> dict[str, object]:
        """Same shape the statement parser produces, so downstream is identical."""
        return {
            "value_date": self.value_date.isoformat(),
            "amount_paise": self.amount_paise,
            "direction": "dr",
            "narration": self.narration,
            "source": {"kind": "sms_alert", "bank": self.bank},
        }


def _to_paise(raw: str) -> int:
    return int(round(float(raw.replace(",", "")) * 100))


def _find_date(text: str, *, fallback: datetime) -> datetime:
    for pattern, fmt in _DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        day, mon, year = m.groups()
        if len(year) == 2:
            year = f"20{year}"
        try:
            return datetime.strptime(f"{day}-{mon}-{year}", fmt.replace("/", "-")).replace(
                tzinfo=UTC
            )
        except ValueError:
            continue
    return fallback


def _merchant(text: str) -> str | None:
    m = _MERCHANT.search(text)
    if not m:
        return None
    name = _NOISE_TAIL.sub("", m.group(1)).strip(" .-_")
    return " ".join(name.split()) or None


def parse_alert(
    text: str, *, bank: str | None = None, received_at: datetime | None = None
) -> ParsedSms | None:
    """One SMS → a debit row, or None when it is not a debit alert.

    Returning None rather than raising is deliberate: an inbox is mostly noise,
    and a parser that throws on an OTP is unusable over real data.
    """
    body = " ".join(text.split())
    low = body.lower()

    if not re.search(_DEBIT_WORDS, low):
        return None
    # a message that only mentions a credit is not ours; if both appear, the
    # debit word decides, since transfer alerts often name both sides
    if re.search(_CREDIT_WORDS, low) and not re.search(_DEBIT_WORDS, low):
        return None
    if "otp" in low or "balance is" in low:
        return None

    amount = re.search(_AMOUNT, low)
    if not amount:
        return None

    merchant = _merchant(body)
    if not merchant:
        return None

    account = _ACCOUNT.search(body)
    return ParsedSms(
        value_date=_find_date(body, fallback=received_at or datetime.now(UTC)),
        amount_paise=_to_paise(amount.group(1)),
        narration=merchant.upper(),
        account_ref=account.group(1) if account else None,
        bank=bank,
    )


def parse_inbox(
    messages: list[dict[str, object]], *, received_at: datetime | None = None
) -> dict[str, object]:
    """Parse a batch. Reports what it skipped instead of hiding it."""
    rows, skipped = [], 0
    for msg in messages:
        parsed = parse_alert(
            str(msg.get("text", "")),
            bank=str(msg.get("sender") or "") or None,
            received_at=received_at,
        )
        if parsed is None:
            skipped += 1
            continue
        rows.append(parsed.as_row())
    return {"rows": rows, "parsed": len(rows), "skipped": skipped}
