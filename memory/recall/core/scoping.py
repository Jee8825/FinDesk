"""Cross-agent memory scoping — the permission layer.

In multi-agent systems each agent typically has siloed memory with no persistent
cross-agent sharing. Recall defines four scopes so agents in the same deployment
can share what should be shared and isolate what should not:

* ``private``    — read/write: originating agent/user only.
* ``team``       — read/write: all agents in a team (e.g. one LangGraph pipeline).
* ``global``     — read: any agent; write/promote: orchestrator only.
* ``user-owned`` — read: user + any agent; delete: user only. Doubles as the
  GDPR-visible tier (``GET /memory/user-owned``).

Read visibility is enforced in :func:`recall.core.repository._visibility_clause`
during retrieval. This module centralizes the *write/promotion* rules.
"""

from __future__ import annotations

from recall.core.types import Scope

SCOPES: tuple[Scope, ...] = ("private", "team", "global", "user-owned")


class ScopeError(PermissionError):
    """Raised when a scope transition or write violates the permission model."""


def can_promote(*, target_scope: Scope, is_orchestrator: bool, team_id: str | None) -> bool:
    """Whether a promotion to ``target_scope`` is permitted.

    * Promoting to ``global`` requires the orchestrator role.
    * Promoting to ``team`` requires a ``team_id``.
    * ``private`` / ``user-owned`` are always allowed.
    """
    if target_scope == "global":
        return is_orchestrator
    if target_scope == "team":
        return team_id is not None
    return True


def validate_promotion(*, target_scope: Scope, is_orchestrator: bool, team_id: str | None) -> None:
    if target_scope not in SCOPES:
        raise ScopeError(f"unknown scope: {target_scope}")
    if not can_promote(
        target_scope=target_scope, is_orchestrator=is_orchestrator, team_id=team_id
    ):
        raise ScopeError(
            f"promotion to '{target_scope}' not permitted "
            f"(orchestrator={is_orchestrator}, team_id={team_id})"
        )
