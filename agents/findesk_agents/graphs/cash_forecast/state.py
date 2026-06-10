"""Typed state for the cash_forecast graph."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from findesk_agents.backend_client import BackendClient
from findesk_agents.events import EventEmitter
from findesk_agents.memoryclient import MemoryClient


class ForecastState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    run_id: str
    emitter: EventEmitter
    backend: BackendClient
    memory: MemoryClient

    opening_balance_paise: int = 0
    open_invoices: list[dict[str, Any]] = Field(default_factory=list)
    debits: list[dict[str, Any]] = Field(default_factory=list)
    avg_late_by_client: dict[str, float] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
