"""Memory scope-key conventions (contracts/memory.md) — shared across layers."""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def vendor_slug(hint: str | None, narration: str = "") -> str:
    """Stable vendor scope slug from a statement hint (else narration head).

    Both the agents' categorizer and the backend's correction endpoint must
    produce identical slugs, or corrections would never be recalled.
    """
    base = (hint or narration)[:40].lower()
    return _SLUG_RE.sub("-", base).strip("-") or "unknown"


def vendor_scope(hint: str | None, narration: str = "") -> str:
    return f"vendor:{vendor_slug(hint, narration)}"
