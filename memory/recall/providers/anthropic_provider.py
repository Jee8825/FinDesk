"""Anthropic (Claude) LLM provider.

Anthropic does not offer an embedding model, so when ``llm_provider=anthropic``
the ``embedding_provider`` must be set to a provider that does (e.g. ``qwen`` or
``openai``). The factory enforces nothing here; it simply builds each side from
its own configured provider.
"""

from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

from recall.config import Settings
from recall.providers._structured import json_with_retry
from recall.providers.base import LLMProvider, ProviderError, Role, T

_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    reraise=True,
)


class AnthropicLLM(LLMProvider):
    def __init__(self, *, api_key: str, heavy_model: str, light_model: str) -> None:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover
            raise ProviderError(
                "anthropic", "install recall[anthropic] to use the Anthropic provider"
            ) from exc
        self.name = "anthropic"
        self._client = AsyncAnthropic(api_key=api_key)
        self._models = {"heavy": heavy_model, "light": light_model}

    @_RETRY
    async def _raw(
        self, prompt: str, *, role: Role, system: str | None, temperature: float, max_tokens: int
    ) -> str:
        try:
            resp = await self._client.messages.create(
                model=self._models[role],
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(self.name, f"messages.create failed: {exc}", exc) from exc
        return "".join(b.text for b in resp.content if b.type == "text")

    async def complete(
        self,
        prompt: str,
        *,
        role: Role = "heavy",
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        return await self._raw(
            prompt, role=role, system=system, temperature=temperature, max_tokens=max_tokens or 2048
        )

    async def complete_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        role: Role = "heavy",
        system: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        async def call(p: str) -> str:
            return await self._raw(
                p, role=role, system=system, temperature=temperature, max_tokens=4096
            )

        return await json_with_retry(call, prompt, schema)

    async def classify(
        self,
        prompt: str,
        labels: list[str],
        *,
        role: Role = "light",
        system: str | None = None,
    ) -> str:
        instruction = (
            f"Choose exactly one label and reply with only that label:\n{labels}\n\n{prompt}"
        )
        out = (await self._raw(
            instruction, role=role, system=system, temperature=0.0, max_tokens=16
        )).strip()
        for label in labels:
            if label.lower() in out.lower():
                return label
        return labels[0]


def build_anthropic_llm(settings: Settings) -> AnthropicLLM:
    import os

    return AnthropicLLM(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        heavy_model=settings.llm_heavy_model,
        light_model=settings.llm_light_model,
    )
