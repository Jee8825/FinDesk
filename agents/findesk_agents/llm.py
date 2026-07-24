"""LLM provider for the agents layer — OpenAI-compatible, multi-provider.

Returns ``None`` when no key is configured: every caller must work without an
LLM (the roadmap's deterministic-fallback rule). No vendor SDK — plain httpx
against the OpenAI chat schema, so Groq/OpenRouter/OpenAI/vLLM/Ollama are all
one env change.

Providers are tried **in order** and the first usable answer wins. That matters
in practice: the free tiers this runs on are day-capped (Groq ~1K req/day), and
a mid-demo 429 must degrade to a second provider before it degrades to
deterministic-only. Which model actually answered is recorded on ``.model`` as
``provider:model`` — that string lands in the proposal's ``checker`` field, so
the audit trail names the judge, not just "an LLM".
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from findesk_agents.config import get_settings

log = logging.getLogger("findesk.llm")

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

Role = Literal["heavy", "light"]


def _first_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object in ``text``, ignoring anything around it.

    Models intermittently wrap a correct answer in prose, or append a second
    object after it — observed live on llama-3.3-70b, where plain ``json.loads``
    raised "Extra data" on an answer that was otherwise exactly right and cost a
    needless fallback hop. ``raw_decode`` stops at the first complete value.
    """
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("no json object found", text, 0)
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise json.JSONDecodeError("expected a json object", text, start)
    return obj


def render_prompt(name: str, **kwargs: str) -> str:
    """Load prompts/<name>.md by name (hard rule #3: no inline prompts)."""
    path = _PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace("{" + key + "}", value)
    return text


@dataclass(frozen=True)
class Candidate:
    """One (provider, endpoint, key, model) the chain may try."""

    provider: str
    base_url: str
    api_key: str
    model: str

    @property
    def provenance(self) -> str:
        return f"{self.provider}:{self.model}"


class ChatLLM:
    """An ordered candidate chain. First candidate to answer usably wins.

    ``.model`` is the provenance (``provider:model``) of the candidate that
    answered the most recent call — read it *after* ``complete_json`` to record
    who judged. Instances are single-run scoped (``get_llm`` builds a fresh one
    per call), so this is not shared mutable state across concurrent runs.
    """

    def __init__(self, candidates: list[Candidate], *, timeout: float = 30.0) -> None:
        if not candidates:
            raise ValueError("ChatLLM needs at least one candidate")
        self._candidates = candidates
        self._timeout = timeout
        self.model = candidates[0].provenance

    @property
    def chain(self) -> list[str]:
        """Provenance of every candidate, in try order (for logs/tests)."""
        return [c.provenance for c in self._candidates]

    async def _attempt(
        self, cand: Candidate, prompt: str, max_tokens: int
    ) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{cand.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {cand.api_key}"},
                    json={
                        "model": cand.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                        "max_tokens": max_tokens,
                    },
                )
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"]
            fence = _FENCE_RE.search(text)
            return _first_json_object(fence.group(1) if fence else text)
        except (httpx.HTTPError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            log.warning("llm candidate %s failed (%s)", cand.provenance, exc)
            return None

    async def complete_json(self, prompt: str, *, max_tokens: int = 1024) -> dict[str, Any] | None:
        """One chat turn, parsed as JSON, walking the chain. None = all failed."""
        for cand in self._candidates:
            result = await self._attempt(cand, prompt, max_tokens)
            if result is not None:
                self.model = cand.provenance
                return result
        log.warning(
            "all %d llm candidates failed — degrading to deterministic path",
            len(self._candidates),
        )
        return None


def _candidates(role: Role) -> list[Candidate]:
    """Configured providers in priority order. Empty = deterministic-only."""
    s = get_settings()
    out: list[Candidate] = []
    if s.groq_api_key:
        out.append(
            Candidate(
                "groq",
                s.groq_base_url,
                s.groq_api_key,
                s.llm_heavy_model if role == "heavy" else s.llm_light_model,
            )
        )
    if s.openrouter_api_key:
        out.append(
            Candidate(
                "openrouter",
                s.openrouter_base_url,
                s.openrouter_api_key,
                s.openrouter_heavy_model if role == "heavy" else s.openrouter_light_model,
            )
        )
    return out


def get_llm(role: Role = "heavy") -> ChatLLM | None:
    """The chain for a role, or None when no provider is configured."""
    cands = _candidates(role)
    return ChatLLM(cands) if cands else None


def get_critic_llm() -> ChatLLM | None:
    """Heavy-role chain — the critic's judgment seat."""
    return get_llm("heavy")
