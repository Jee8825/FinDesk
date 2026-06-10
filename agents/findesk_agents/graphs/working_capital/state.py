"""Typed state for the working_capital graph."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from findesk_agents.backend_client import BackendClient
from findesk_agents.events import EventEmitter
from findesk_agents.memoryclient import MemoryClient


class WorkingCapitalState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    run_id: str
    emitter: EventEmitter
    backend: BackendClient
    memory: MemoryClient

    open_invoices: list[dict[str, Any]] = Field(default_factory=list)
    gap: dict[str, Any] | None = None
    avg_late_by_client: dict[str, float] = Field(default_factory=dict)
    options: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
