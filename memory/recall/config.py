"""Central configuration for Recall, loaded from environment (prefix ``RECALL_``).

A single :class:`Settings` instance is the source of truth for connection
strings, provider selection, and engine-tuning constants. Modules should depend
on :func:`get_settings` rather than reading ``os.environ`` directly so that
tests can override cleanly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["qwen", "openai", "anthropic", "local"]
Tier = Literal["episodic", "semantic", "procedural"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RECALL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    log_level: str = "INFO"

    # --- Datastores ---
    postgres_dsn: str = "postgresql+asyncpg://recall:recall@localhost:5432/recall"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "recall-neo4j"
    redis_url: str = "redis://localhost:6379/0"

    # --- Provider selection ---
    llm_provider: ProviderName = "qwen"
    embedding_provider: ProviderName = "qwen"
    llm_heavy_model: str = "qwen-max"
    llm_light_model: str = "qwen-plus"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024
    local_base_url: str = "http://localhost:11434/v1"

    # --- Engine tuning ---
    # Per-tier exponential decay rate lambda, in units of 1/day.
    decay_lambda_episodic: float = 0.35
    decay_lambda_semantic: float = 0.02
    decay_lambda_procedural: float = 0.001
    # Multiplier applied to strength on each retrieval (r > 1).
    reinforcement_factor: float = 1.25
    # Strength below which a memory is soft-deleted (tombstoned).
    tombstone_threshold: float = 0.05
    # Cosine distance below which two semantic facts are "about the same thing".
    conflict_distance_threshold: float = 0.25
    # Confidence above which decay is paused and the belief is "crystallized".
    crystallize_threshold: float = 0.95

    # --- Retrieval / prefetch ---
    default_token_budget: int = 2000
    prefetch_window_turns: int = 3
    prefetch_cache_ttl_seconds: int = 900

    def decay_lambda(self, tier: Tier) -> float:
        """Return the decay constant for a given memory tier."""
        return {
            "episodic": self.decay_lambda_episodic,
            "semantic": self.decay_lambda_semantic,
            "procedural": self.decay_lambda_procedural,
        }[tier]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""
    return Settings()
