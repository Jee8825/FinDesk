"""LLM provider for the agents layer — OpenAI-compatible, Groq-first.

Returns ``None`` when no key is configured: every caller must work without an
LLM (the roadmap's deterministic-fallback rule). No vendor SDK — plain httpx
against the OpenAI chat schema, so Groq/OpenAI/vLLM/Ollama are all one env
change.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from findesk_agents.config import get_settings

log = logging.getLogger("findesk.llm")

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def render_prompt(name: str, **kwargs: str) -> str:
    """Load prompts/<name>.md by name (hard rule #3: no inline prompts)."""
    path = _PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace("{" + key + "}", value)
    return text


class ChatLLM:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model

    async def complete_json(self, prompt: str, *, max_tokens: int = 1024) -> dict[str, Any] | None:
        """One chat turn, parsed as JSON. None on any failure (callers degrade)."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                        "max_tokens": max_tokens,
                    },
                )
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"]
            fence = _FENCE_RE.search(text)
            return json.loads(fence.group(1) if fence else text)
        except (httpx.HTTPError, OSError, KeyError, json.JSONDecodeError) as exc:
            log.warning("llm call failed, degrading to deterministic path (%s)", exc)
            return None


def get_critic_llm() -> ChatLLM | None:
    settings = get_settings()
    if not settings.groq_api_key:
        return None
    return ChatLLM(
        base_url=settings.groq_base_url,
        api_key=settings.groq_api_key,
        model=settings.llm_heavy_model,
    )
