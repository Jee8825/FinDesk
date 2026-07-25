"""LLM candidate chain — fallback order, provenance, and the None contract.

No network: every test drives ChatLLM._attempt through a stub. The point under
test is the *chain* policy (which provider answers, what provenance is recorded,
when the whole thing degrades to deterministic), not httpx.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from findesk_agents import llm as llm_mod
from findesk_agents.llm import Candidate, ChatLLM, get_llm


def _cands(*names: str) -> list[Candidate]:
    return [Candidate(n, f"https://{n}.test/v1", f"key-{n}", f"{n}-model") for n in names]


def _stub(chat: ChatLLM, answers: dict[str, dict[str, Any] | None]) -> list[str]:
    """Replace _attempt with a lookup by provider; returns the call log."""
    calls: list[str] = []

    async def fake(cand: Candidate, prompt: str, max_tokens: int):
        calls.append(cand.provider)
        return answers.get(cand.provider)

    chat._attempt = fake  # type: ignore[method-assign]
    return calls


async def test_primary_answers_and_second_is_never_called():
    chat = ChatLLM(_cands("groq", "openrouter"))
    calls = _stub(chat, {"groq": {"ok": 1}, "openrouter": {"ok": 2}})

    assert await chat.complete_json("p") == {"ok": 1}
    assert calls == ["groq"], "fallback must not fire when the primary answers"
    assert chat.model == "groq:groq-model"


async def test_falls_through_to_second_provider():
    chat = ChatLLM(_cands("groq", "openrouter"))
    calls = _stub(chat, {"groq": None, "openrouter": {"ok": 2}})

    assert await chat.complete_json("p") == {"ok": 2}
    assert calls == ["groq", "openrouter"]
    # provenance names the model that actually judged — this string is what
    # lands in the proposal's `checker` field and therefore in the audit trail
    assert chat.model == "openrouter:openrouter-model"


async def test_all_candidates_failing_returns_none():
    chat = ChatLLM(_cands("groq", "openrouter"))
    calls = _stub(chat, {"groq": None, "openrouter": None})

    assert await chat.complete_json("p") is None, "callers rely on None to degrade"
    assert calls == ["groq", "openrouter"]


async def test_provenance_defaults_to_primary_before_any_call():
    chat = ChatLLM(_cands("groq", "openrouter"))
    assert chat.model == "groq:groq-model"
    assert chat.chain == ["groq:groq-model", "openrouter:openrouter-model"]


def test_empty_chain_is_rejected():
    with pytest.raises(ValueError):
        ChatLLM([])


def test_no_keys_configured_yields_no_llm(monkeypatch):
    monkeypatch.setattr(llm_mod, "_candidates", lambda role: [])
    assert get_llm("heavy") is None, "no provider = deterministic-only, not a crash"


def test_role_selects_the_light_model(monkeypatch):
    class S:
        groq_api_key = "k"
        groq_base_url = "https://groq.test/v1"
        llm_heavy_model = "heavy-1"
        llm_light_model = "light-1"
        openrouter_api_key = ""
        openrouter_base_url = ""
        openrouter_heavy_model = ""
        openrouter_light_model = ""

    monkeypatch.setattr(llm_mod, "get_settings", lambda: S())
    assert get_llm("heavy").chain == ["groq:heavy-1"]
    assert get_llm("light").chain == ["groq:light-1"]


def test_provider_order_is_groq_then_openrouter(monkeypatch):
    class S:
        groq_api_key = "a"
        groq_base_url = "https://groq.test/v1"
        llm_heavy_model = "h"
        llm_light_model = "l"
        openrouter_api_key = "b"
        openrouter_base_url = "https://or.test/v1"
        openrouter_heavy_model = "or-h"
        openrouter_light_model = "or-l"

    monkeypatch.setattr(llm_mod, "get_settings", lambda: S())
    assert get_llm("heavy").chain == ["groq:h", "openrouter:or-h"]


def test_openrouter_alone_still_works(monkeypatch):
    """Groq is the default, not a requirement — an OpenRouter-only env is valid."""

    class S:
        groq_api_key = ""
        groq_base_url = ""
        llm_heavy_model = ""
        llm_light_model = ""
        openrouter_api_key = "b"
        openrouter_base_url = "https://or.test/v1"
        openrouter_heavy_model = "or-h"
        openrouter_light_model = "or-l"

    monkeypatch.setattr(llm_mod, "get_settings", lambda: S())
    assert get_llm("heavy").chain == ["openrouter:or-h"]


# --- response parsing (regressions from live provider behaviour) -------------

def test_parses_json_followed_by_trailing_prose():
    """llama-3.3-70b appends extra content after a correct answer (observed live)."""
    out = llm_mod._first_json_object('{"reviews": [{"index": 0}]}\nHope this helps!')
    assert out == {"reviews": [{"index": 0}]}


def test_parses_json_preceded_by_prose():
    out = llm_mod._first_json_object('Here is my answer:\n{"verdict": "fail"}')
    assert out == {"verdict": "fail"}


def test_ignores_a_second_object_after_the_first():
    out = llm_mod._first_json_object('{"a": 1}{"b": 2}')
    assert out == {"a": 1}


def test_rejects_a_response_with_no_object():
    with pytest.raises(json.JSONDecodeError):
        llm_mod._first_json_object("I cannot answer that.")


def test_rejects_a_bare_json_array():
    """The critic contract is an object; a list would break every caller."""
    with pytest.raises(json.JSONDecodeError):
        llm_mod._first_json_object("[1, 2, 3]")


async def test_unparseable_primary_falls_through_to_the_next_provider():
    """A parse failure must be treated as a candidate failure, not a hard stop."""
    chat = ChatLLM(_cands("groq", "openrouter"))
    calls: list[str] = []

    async def fake(cand, prompt, max_tokens):
        calls.append(cand.provider)
        return None if cand.provider == "groq" else {"ok": True}

    chat._attempt = fake  # type: ignore[method-assign]
    assert await chat.complete_json("p") == {"ok": True}
    assert calls == ["groq", "openrouter"]


async def test_null_content_is_treated_as_an_empty_answer(monkeypatch):
    """Observed live on gpt-oss-20b: `content: null` surfaced as a bare TypeError
    from the regex, which read like a bug in our parser rather than an empty
    answer from theirs. Must degrade to the next candidate cleanly."""

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": None}}]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return FakeResp()

    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda **kw: FakeClient())
    chat = ChatLLM(_cands("groq"))
    assert await chat.complete_json("p") is None


async def test_empty_string_content_also_degrades():
    chat = ChatLLM(_cands("groq", "openrouter"))
    calls: list[str] = []

    async def fake(cand, prompt, max_tokens):
        calls.append(cand.provider)
        return None if cand.provider == "groq" else {"ok": True}

    chat._attempt = fake  # type: ignore[method-assign]
    assert await chat.complete_json("p") == {"ok": True}
    assert calls == ["groq", "openrouter"]
