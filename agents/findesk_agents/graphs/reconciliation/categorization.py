"""A3 categorization — pure functions: rules lexicon + memory-driven claims.

Priority order per transaction:
1. **memory** — a remembered (possibly crystallized) ``vendor_category`` claim
   for this vendor. Human corrections become these claims, so the agent learns
   the tenant's own taxonomy and stops second-guessing settled vendors.
2. **rule** — the deterministic narration lexicon below.
3. otherwise: left uncategorized (an exception, never a guess).

Crystallization (confidence ≥ 0.95 in Recall) raises memory assignments to
near-certain confidence; ordinary claims assign at 0.85.
"""

from __future__ import annotations

import re
from typing import Any

from findesk_shared import vendor_slug as _shared_vendor_slug

CRYSTALLIZED_CONFIDENCE = 0.97
MEMORY_CONFIDENCE = 0.85
CRYSTALLIZE_THRESHOLD = 0.95

# (pattern, category_code, confidence) — first hit wins; tuned for Indian SME
# narrations. Grows with real statement quirks, never with guesses.
LEXICON: list[tuple[re.Pattern[str], str, float]] = [
    (
        re.compile(r"\bAWS\b|AMAZON WEB|GOOGLE CLOUD|GCP|AZURE|DIGITALOCEAN", re.I),
        "software_cloud",
        0.92,
    ),
    (re.compile(r"SAAS|SUBSCRIPTION|ZOHO|GITHUB|SLACK|NOTION|FIGMA", re.I), "software_cloud", 0.88),
    (re.compile(r"SALARY|PAYROLL|STAFF BATCH|WAGES", re.I), "payroll", 0.95),
    (re.compile(r"RENT\b|WEWORK|AWFIS|COWORK", re.I), "rent", 0.92),
    (re.compile(r"ELECTRICITY|BESCOM|MSEB|TATA POWER|POWER BILL", re.I), "utilities", 0.92),
    (re.compile(r"GST PAYMENT|GSTR|CBIC", re.I), "taxes_gst", 0.95),
    (re.compile(r"TDS DEPOSIT|TDS PAYMENT|194[A-Z]", re.I), "taxes_tds", 0.95),
    (re.compile(r"ZOMATO|SWIGGY|LUNCH|DINNER|CAFETERIA", re.I), "staff_welfare", 0.85),
    (re.compile(r"UBER|OLA\b|IRCTC|INDIGO|AIR INDIA|MAKEMYTRIP", re.I), "travel", 0.88),
    (re.compile(r"CA FEES|AUDIT FEE|LEGAL|CONSULTANT", re.I), "professional_fees", 0.85),
    (re.compile(r"BANK CHARGES|SMS CHARGES|AMC CHARGES|NEFT CHARGES", re.I), "bank_charges", 0.95),
    (re.compile(r"GOOGLE ADS|META ADS|FACEBOOK|LINKEDIN ADS", re.I), "marketing", 0.88),
]

_CLAIM_RE = re.compile(r"categorized as ([a-z0-9_]+)")


def vendor_slug(txn: dict[str, Any]) -> str:
    """Stable memory scope key for a debit's vendor (shared convention)."""
    return _shared_vendor_slug(txn.get("counterparty_hint"), txn.get("narration", ""))


def parse_category_claims(memories: list[dict[str, Any]]) -> tuple[str, float] | None:
    """Best (code, claim_confidence) from vendor_category memory contents."""
    best: tuple[str, float] | None = None
    for m in memories:
        match = _CLAIM_RE.search(m.get("content", ""))
        if not match:
            continue
        conf = float(m.get("confidence") or 0.5)
        if best is None or conf > best[1]:
            best = (match.group(1), conf)
    return best


def rule_category(narration: str) -> tuple[str, float] | None:
    for pattern, code, conf in LEXICON:
        if pattern.search(narration):
            return (code, conf)
    return None


def categorize(
    txns: list[dict[str, Any]],
    memory_claims: dict[str, tuple[str, float]],
    valid_codes: set[str],
) -> list[dict[str, Any]]:
    """Assign categories to uncategorized debits. Returns persistence items."""
    items: list[dict[str, Any]] = []
    for txn in txns:
        if txn["direction"] != "dr" or txn.get("category_code"):
            continue
        slug = vendor_slug(txn)
        label = (txn.get("counterparty_hint") or txn.get("narration", ""))[:40]
        claim = memory_claims.get(slug)
        if claim and claim[0] in valid_codes:
            code, claim_conf = claim
            confidence = (
                CRYSTALLIZED_CONFIDENCE
                if claim_conf >= CRYSTALLIZE_THRESHOLD
                else MEMORY_CONFIDENCE
            )
            items.append(
                {
                    "bank_transaction_id": txn["id"],
                    "category_code": code,
                    "source": "memory",
                    "confidence": confidence,
                    "vendor_slug": slug,
                    "vendor_label": label,
                }
            )
            continue
        rule = rule_category(txn.get("narration", ""))
        if rule and rule[0] in valid_codes:
            items.append(
                {
                    "bank_transaction_id": txn["id"],
                    "category_code": rule[0],
                    "source": "rule",
                    "confidence": rule[1],
                    "vendor_slug": slug,
                    "vendor_label": label,
                }
            )
    return items
