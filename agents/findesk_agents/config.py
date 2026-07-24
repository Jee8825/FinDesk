"""Worker settings — env-driven, mirrors backend stream names."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_redis_url: str = "redis://localhost:6380/0"
    backend_base_url: str = "http://localhost:8080"
    internal_api_token: str = "dev-internal-token"
    recall_base_url: str = "http://localhost:8000"
    jobs_stream_interactive: str = "agents:interactive"
    jobs_consumer_group: str = "workers"
    events_stream: str = "agents:events"
    jobs_dead_stream: str = "agents:dead"  # poison jobs after max deliveries
    # STABLE across restarts — a random name orphans this worker's pending
    # entries forever when it dies (nobody reclaims a stranger's PEL).
    worker_consumer_name: str = "worker-main"
    worker_max_deliveries: int = 3
    worker_reclaim_idle_ms: int = 60_000
    worker_reclaim_every_s: int = 30

    # LLM providers, tried in this order; no key at all = deterministic-only.
    # Both free tiers are day-capped, so the second exists to survive a 429
    # mid-demo rather than silently dropping the AI out of the run.
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_heavy_model: str = "llama-3.3-70b-versatile"
    llm_light_model: str = "llama-3.1-8b-instant"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # both verified to return strict JSON on prompts/agents/critic@v1 (2026-07-24)
    openrouter_heavy_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    openrouter_light_model: str = "openai/gpt-oss-20b:free"

    otel_service_name: str = "findesk-agents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
