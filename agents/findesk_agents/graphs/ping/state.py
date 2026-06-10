"""Typed LangGraph state for the ping graph."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from findesk_agents.events import EventEmitter


class PingState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: str
    run_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    emitter: EventEmitter
    plan: list[str] = Field(default_factory=list)
    executed: list[str] = Field(default_factory=list)
    summary: str = ""
