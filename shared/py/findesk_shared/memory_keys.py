"""Memory scope-key conventions (contracts/memory.md) — shared across layers."""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")
# month tokens and bare numbers make the same vendor look different across
# billing cycles ("AWS ... APR" vs "AWS ... JUL") — strip them before slugging
_NOISE_TOKENS = {
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec", "january", "february", "march", "april", "june",
    "july", "august", "september", "october", "november", "december",
    "q1", "q2", "q3", "q4",
}


def vendor_slug(hint: str | None, narration: str = "") -> str:
    """Stable vendor scope slug from a statement hint (else narration head).

    Every layer (categorizer, anomaly scan, correction endpoint) must produce
    identical slugs for the same vendor, or memories would never be recalled.
    """
    base = (hint or narration)[:40].lower()
    tokens = [
        t
        for t in _SLUG_RE.sub(" ", base).split()
        if t not in _NOISE_TOKENS and not t.isdigit()
    ]
    return "-".join(tokens) or "unknown"


def vendor_scope(hint: str | None, narration: str = "") -> str:
    return f"vendor:{vendor_slug(hint, narration)}"


_LATE_RE = re.compile(r"paid\s+(\d+)\s+days?\s+(late|early)")


def late_phrase(delta_days: int) -> str:
    """Write-side twin of parse_late_days — every learn path builds its
    payment-timing claims through this so writer and parser cannot drift.
    0 renders as "0 days early" (parses back to 0)."""
    return f"{delta_days} days late" if delta_days > 0 else f"{-delta_days} days early"


def parse_late_days(contents: list[str]) -> list[int]:
    """Extract payment-timing observations from memory claim texts.

    'paid N days late' → +N, 'paid N days early' → −N. The claim wording is
    written by the learn paths; this parser is their read-side twin — they
    live in shared so they cannot drift apart.
    """
    out = []
    for c in contents:
        m = _LATE_RE.search(c)
        if m:
            n = int(m.group(1))
            out.append(n if m.group(2) == "late" else -n)
    return out
