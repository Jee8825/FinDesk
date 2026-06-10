"""Typed state for the reconciliation graph (Phase 1: rules-only)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from findesk_agents.backend_client import BackendClient
from findesk_agents.events import EventEmitter
from findesk_agents.memoryclient import MemoryClient


class ReconState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    run_id: str
    document_id: str
    emitter: EventEmitter
    backend: BackendClient
    memory: MemoryClient

    # produced along the way
    parsed: list[dict[str, Any]] = Field(default_factory=list)
    parse_meta: dict[str, Any] = Field(default_factory=dict)
    ingested: dict[str, int] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    proposals: list[dict[str, Any]] = Field(default_factory=list)
    categorized: list[dict[str, Any]] = Field(default_factory=list)
    vendor_claims_known: list[str] = Field(default_factory=list)  # slugs with existing claims
    commit_result: dict[str, Any] = Field(default_factory=dict)
    memory_notes: list[str] = Field(default_factory=list)
    summary: str = ""
