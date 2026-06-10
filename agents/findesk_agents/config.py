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

    otel_service_name: str = "findesk-agents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
