"""Typed state for the month_end_close graph."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from findesk_agents.backend_client import BackendClient
from findesk_agents.events import EventEmitter
from findesk_agents.memoryclient import MemoryClient


class CloseState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    run_id: str
    emitter: EventEmitter
    backend: BackendClient
    # Deliberate deviation from the recall-before-reason rule (like the
    # enforcer): the close is evidence *composition* over deterministic
    # engines — memory must never move a checklist verdict. Field present
    # because the worker's common state carries it; nodes never touch it.
    memory: MemoryClient

    period: str = ""
    checklist: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
