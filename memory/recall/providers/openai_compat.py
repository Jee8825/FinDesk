"""OpenAI-compatible provider.

This single implementation backs three configured providers, which differ only
by base URL and credentials:

* ``qwen``   — DashScope's OpenAI-compatible endpoint (Qwen-Max / Qwen-Plus /
  text-embedding-v3).
* ``openai`` — OpenAI proper.
* ``local``  — Ollama / vLLM / any server exposing the OpenAI schema.

The ``openai`` Python SDK is an optional dependency; it is imported lazily so
that installing only one provider's extras is enough.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenacity import retry, stop_after_attempt, wait_exponential

from recall.config import Settings
from recall.providers._structured import json_with_retry
from recall.providers.base import LLMProvider, ProviderError, Role, T

if TYPE_CHECKING:
    from openai import AsyncOpenAI


def _client(base_url: str | None, api_key: str) -> AsyncOpenAI:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:  # pragma: no cover - import guard
        raise ProviderError(
            "openai-compat",
            "the 'openai' package is required; install recall[openai] or recall[qwen]",
        ) from exc
    return AsyncOpenAI(base_url=base_url, api_key=api_key or "not-needed")


_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    reraise=True,
)


class OpenAICompatLLM(LLMProvider):
    """Chat-completion provider speaking the OpenAI API."""

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str | None,
        heavy_model: str,
        light_model: str,
    ) -> None:
        self.name = name
        self._client = _client(base_url, api_key)
        self._models = {"heavy": heavy_model, "light": light_model}

    def _model(self, role: Role) -> str:
        return self._models[role]

    @_RETRY
    async def _raw(
        self,
        prompt: str,
        *,
        role: Role,
        system: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = await self._client.chat.completions.create(
                model=self._model(role),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - normalize all SDK errors
            raise ProviderError(self.name, f"chat completion failed: {exc}", exc) from exc
        return resp.choices[0].message.content or ""

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
            prompt, role=role, system=system, temperature=temperature, max_tokens=max_tokens
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
                p, role=role, system=system, temperature=temperature, max_tokens=None
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
            f"Choose exactly one label from this list and reply with only that label:\n"
            f"{labels}\n\n{prompt}"
        )
        out = (await self._raw(
            instruction, role=role, system=system, temperature=0.0, max_tokens=16
        )).strip()
        # Be forgiving: match the first label that appears in the response.
        for label in labels:
            if label.lower() in out.lower():
                return label
        return labels[0]


class OpenAICompatEmbedder:
    """Embedding provider speaking the OpenAI API."""

    def __init__(
        self, *, name: str, api_key: str, base_url: str | None, model: str, dim: int
    ) -> None:
        self.name = name
        self.dim = dim
        self._model = model
        self._client = _client(base_url, api_key)

    @_RETRY
    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = await self._client.embeddings.create(model=self._model, input=texts)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(self.name, f"embedding failed: {exc}", exc) from exc
        return [d.embedding for d in resp.data]


# DashScope's OpenAI-compatible base URL.
DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


def build_openai_compat_llm(settings: Settings, provider: str) -> OpenAICompatLLM:
    import os

    if provider == "qwen":
        return OpenAICompatLLM(
            name="qwen",
            api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            base_url=DASHSCOPE_BASE_URL,
            heavy_model=settings.llm_heavy_model,
            light_model=settings.llm_light_model,
        )
    if provider == "local":
        return OpenAICompatLLM(
            name="local",
            api_key="not-needed",
            base_url=settings.local_base_url,
            heavy_model=settings.llm_heavy_model,
            light_model=settings.llm_light_model,
        )
    # openai
    return OpenAICompatLLM(
        name="openai",
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=None,
        heavy_model=settings.llm_heavy_model,
        light_model=settings.llm_light_model,
    )


def build_openai_compat_embedder(settings: Settings, provider: str) -> OpenAICompatEmbedder:
    import os

    if provider == "qwen":
        return OpenAICompatEmbedder(
            name="qwen",
            api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            base_url=DASHSCOPE_BASE_URL,
            model=settings.embedding_model,
            dim=settings.embedding_dim,
        )
    if provider == "local":
        return OpenAICompatEmbedder(
            name="local",
            api_key="not-needed",
            base_url=settings.local_base_url,
            model=settings.embedding_model,
            dim=settings.embedding_dim,
        )
    return OpenAICompatEmbedder(
        name="openai",
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=None,
        model=settings.embedding_model,
        dim=settings.embedding_dim,
    )
