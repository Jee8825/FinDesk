"""Typed state for the subscription_scan graph (LeakRadar)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from findesk_agents.backend_client import BackendClient
from findesk_agents.events import EventEmitter
from findesk_agents.memoryclient import MemoryClient


class SubscriptionState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    run_id: str
    emitter: EventEmitter
    backend: BackendClient
    memory: MemoryClient

    mode: str = "business"
    debits: list[dict[str, Any]] = Field(default_factory=list)
    canonical_notes: list[str] = Field(default_factory=list)
    cadences: dict[str, dict[str, Any]] = Field(default_factory=dict)
    duplicates: dict[str, int] = Field(default_factory=dict)
    usage: dict[str, str] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    totals: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
