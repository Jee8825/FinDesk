"""Typed state for the collections graph."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from findesk_agents.backend_client import BackendClient
from findesk_agents.events import EventEmitter
from findesk_agents.memoryclient import MemoryClient


class CollectionsState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    run_id: str
    emitter: EventEmitter
    backend: BackendClient
    memory: MemoryClient

    overdue: list[dict[str, Any]] = Field(default_factory=list)
    sender_name: str = "Accounts, Demo Trading Co"
    drafts: list[dict[str, Any]] = Field(default_factory=list)
    queued: int = 0
    summary: str = ""
