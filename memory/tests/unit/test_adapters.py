"""Unit tests for the framework-agnostic adapter core and LangGraph nodes."""

from __future__ import annotations

import uuid

import pytest
from recall.adapters.base import RecallMemory
from recall.adapters.langgraph_adapter import recall_nodes
from recall.core.types import IngestResult, RetrievedMemory, RetrieveResult


class FakeClient:
    def __init__(self) -> None:
        self.ingested: list[str] = []

    async def ingest(self, *, content, **kwargs):  # noqa: ANN001
        self.ingested.append(content)
        return IngestResult(units=[], conflicts_detected=0)

    async def retrieve(self, *, query, **kwargs):  # noqa: ANN001
        return RetrieveResult(
            memories=[
                RetrievedMemory(
                    id=uuid.uuid4(), content="User deploys on AWS", tier="semantic",
                    score=0.9, strength=0.8, confidence=0.9,
                ),
                RetrievedMemory(
                    id=uuid.uuid4(), content="User maybe likes Go", tier="semantic",
                    score=0.4, strength=0.5, confidence=0.3,
                ),
            ],
            tokens_used=20,
            token_budget=1500,
        )

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_recall_memory_remember_and_recall():
    mem = RecallMemory(user_id="u1", client=FakeClient())
    n = await mem.remember("I deploy on AWS")
    assert n == 0  # fake returns no units
    text = await mem.recall_text("where do I deploy")
    assert "User deploys on AWS" in text
    # Low-confidence memory is hedged.
    assert "(low confidence)" in text


@pytest.mark.asyncio
async def test_langgraph_nodes_inject_and_ingest():
    fake = FakeClient()
    mem = RecallMemory(user_id="u1", client=fake)
    retrieve_node, ingest_node = recall_nodes(user_id="u1", memory=mem)

    state = {"messages": [{"role": "user", "content": "where do I deploy?"}]}
    state = await retrieve_node(state)
    assert "recall_context" in state
    assert "AWS" in state["recall_context"]

    await ingest_node(state)
    assert fake.ingested == ["where do I deploy?"]
