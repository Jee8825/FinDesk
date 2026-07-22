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

    # LLM (Groq or any OpenAI-compatible endpoint). Empty key = deterministic-only.
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_heavy_model: str = "llama-3.3-70b-versatile"

    otel_service_name: str = "findesk-agents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
