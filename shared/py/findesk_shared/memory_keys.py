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
