"""Provider factory.

Engine code calls :func:`get_llm` / :func:`get_embedder` and receives an object
satisfying the :class:`~recall.providers.base.LLMProvider` /
:class:`~recall.providers.base.EmbeddingProvider` protocols. The concrete vendor
is chosen from settings and cached per process.
"""

from __future__ import annotations

from functools import lru_cache

from recall.config import Settings, get_settings
from recall.providers.base import EmbeddingProvider, LLMProvider, ProviderError, Role

__all__ = ["LLMProvider", "EmbeddingProvider", "ProviderError", "Role", "get_llm", "get_embedder"]


def _build_llm(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider
    if provider == "anthropic":
        from recall.providers.anthropic_provider import build_anthropic_llm

        return build_anthropic_llm(settings)
    from recall.providers.openai_compat import build_openai_compat_llm

    return build_openai_compat_llm(settings, provider)


def _build_embedder(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider
    if provider == "anthropic":
        raise ProviderError(
            "anthropic",
            "Anthropic has no embedding model; set RECALL_EMBEDDING_PROVIDER to qwen/openai/local",
        )
    from recall.providers.openai_compat import build_openai_compat_embedder

    return build_openai_compat_embedder(settings, provider)


@lru_cache
def get_llm() -> LLMProvider:
    return _build_llm(get_settings())


@lru_cache
def get_embedder() -> EmbeddingProvider:
    return _build_embedder(get_settings())
