"""Why? composition — memory beliefs merge (pure logic, memoryclient faked)."""

from __future__ import annotations

from typing import Any

from app.api import routes_why


def _fake_retrieve(responses: dict[str, dict[str, dict[str, Any]]]):
    async def retrieve_units(*, tenant_id: str, scope_key: str, query: str, **_: Any):
        return responses.get(scope_key, {})

    return retrieve_units


def _fake_why(chains: dict[str, dict[str, Any] | None]):
    async def why_chain(*, tenant_id: str, memory_id: str):
        return chains.get(memory_id)

    return why_chain


async def test_memory_beliefs_composes_content_and_explanation(monkeypatch):
    monkeypatch.setattr(
        routes_why.memoryclient,
        "retrieve_units",
        _fake_retrieve(
            {
                "vendor:aws": {
                    "m1": {"content": "AWS is software_cloud.", "confidence": 0.9},
                }
            }
        ),
    )
    monkeypatch.setattr(
        routes_why.memoryclient,
        "why_chain",
        _fake_why({"m1": {"explanation": "learned from 3 statements"}}),
    )
    out = await routes_why._memory_beliefs("t1", [("vendor:aws", "aws bill")])
    assert len(out) == 1
    assert out[0].content == "AWS is software_cloud."
    assert out[0].confidence == 0.9
    assert out[0].explanation == "learned from 3 statements"
    assert out[0].scope_key == "vendor:aws"


async def test_memory_beliefs_dedupes_across_scopes_and_caps(monkeypatch):
    units = {f"m{i}": {"content": f"fact {i}", "confidence": 0.5} for i in range(5)}
    monkeypatch.setattr(
        routes_why.memoryclient,
        "retrieve_units",
        _fake_retrieve({"vendor:a": units, "client:c1": {"m0": units["m0"]}}),
    )
    monkeypatch.setattr(routes_why.memoryclient, "why_chain", _fake_why({}))
    out = await routes_why._memory_beliefs(
        "t1", [("vendor:a", "q"), ("client:c1", "q")]
    )
    ids = [b.memory_id for b in out]
    assert len(ids) == len(set(ids)), "same belief must not repeat across scopes"
    assert len(out) <= routes_why.MEMORY_BELIEFS_LIMIT


async def test_memory_beliefs_survives_memory_down(monkeypatch):
    # memoryclient returns {} / None when Recall is unreachable — the why
    # route must degrade to an empty memory section, never raise
    monkeypatch.setattr(routes_why.memoryclient, "retrieve_units", _fake_retrieve({}))
    monkeypatch.setattr(routes_why.memoryclient, "why_chain", _fake_why({}))
    out = await routes_why._memory_beliefs("t1", [("vendor:x", "q")])
    assert out == []
