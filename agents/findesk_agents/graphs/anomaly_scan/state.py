"""Typed state for the anomaly_scan graph."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from findesk_agents.backend_client import BackendClient
from findesk_agents.events import EventEmitter
from findesk_agents.memoryclient import MemoryClient


class AnomalyState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    run_id: str
    emitter: EventEmitter
    backend: BackendClient
    memory: MemoryClient

    debits: list[dict[str, Any]] = Field(default_factory=list)
    memory_baselines: dict[str, list[int]] = Field(default_factory=dict)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    persisted: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
