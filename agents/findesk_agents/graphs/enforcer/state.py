"""Typed state for the enforcer_45day graph."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from findesk_agents.backend_client import BackendClient
from findesk_agents.events import EventEmitter
from findesk_agents.memoryclient import MemoryClient


class EnforcerState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    run_id: str
    emitter: EventEmitter
    backend: BackendClient
    memory: MemoryClient

    transitions: list[dict[str, Any]] = Field(default_factory=list)
    sender_name: str = "Accounts"
    tenant_name: str = ""
    letters_queued: int = 0
    samadhaan_prepared: int = 0
    summary: str = ""
