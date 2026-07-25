"""Close critic — pure invariants between fetch and persist.

The checklist is the artifact a human signs off on; a malformed or
self-inconsistent one is worse than none. Deterministic, no I/O —
unit-tested without a DB (same seat as the forecast critic).
"""

from __future__ import annotations

from typing import Any

REQUIRED_KEYS = {"id", "label", "ok", "severity", "value", "href"}
SEVERITIES = {"block", "warn"}
MIN_CHECKS = 8  # the engine composes at least the eight known evidence checks


def review(checklist: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    checks = checklist.get("checks")
    if not isinstance(checks, list) or len(checks) < MIN_CHECKS:
        return [f"expected ≥{MIN_CHECKS} checks, got {len(checks or [])}"]

    seen_ids: set[str] = set()
    for c in checks:
        missing = REQUIRED_KEYS - set(c)
        if missing:
            problems.append(f"check {c.get('id', '?')} missing {sorted(missing)}")
            continue
        if c["severity"] not in SEVERITIES:
            problems.append(f"check {c['id']} has unknown severity {c['severity']!r}")
        if not isinstance(c["ok"], bool):
            problems.append(f"check {c['id']} ok is not a bool")
        if c["id"] in seen_ids:
            problems.append(f"duplicate check id {c['id']}")
        seen_ids.add(c["id"])

    # cross-check the reducer: blockers/warnings/ready must be exactly
    # derivable from the rows (a drifted summary would mislead the signer)
    blockers = [c["id"] for c in checks if not c.get("ok") and c.get("severity") == "block"]
    warnings = [c["id"] for c in checks if not c.get("ok") and c.get("severity") == "warn"]
    if checklist.get("blockers") != blockers:
        problems.append("blockers list does not match check rows")
    if checklist.get("warnings") != warnings:
        problems.append("warnings list does not match check rows")
    if checklist.get("ready") != (not blockers):
        problems.append("ready flag contradicts blockers")

    chain = next((c for c in checks if c.get("id") == "audit_chain"), None)
    if chain is None:
        problems.append("audit_chain check missing")
    elif chain.get("ok") and not checklist.get("audit_head"):
        problems.append("audit chain ok but no head hash recorded")
    return problems
