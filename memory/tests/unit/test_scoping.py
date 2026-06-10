"""Unit tests for the cross-agent scope permission rules."""

from __future__ import annotations

import pytest
from recall.core import scoping


def test_global_requires_orchestrator():
    assert scoping.can_promote(target_scope="global", is_orchestrator=True, team_id=None)
    assert not scoping.can_promote(target_scope="global", is_orchestrator=False, team_id=None)


def test_team_requires_team_id():
    assert scoping.can_promote(target_scope="team", is_orchestrator=False, team_id="t1")
    assert not scoping.can_promote(target_scope="team", is_orchestrator=False, team_id=None)


def test_private_and_user_owned_always_allowed():
    assert scoping.can_promote(target_scope="private", is_orchestrator=False, team_id=None)
    assert scoping.can_promote(target_scope="user-owned", is_orchestrator=False, team_id=None)


def test_validate_promotion_raises():
    with pytest.raises(scoping.ScopeError):
        scoping.validate_promotion(target_scope="global", is_orchestrator=False, team_id=None)
    # valid path does not raise
    scoping.validate_promotion(target_scope="team", is_orchestrator=False, team_id="t1")
