"""App settings — env-driven, never read os.environ elsewhere."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_database_url: str = "postgresql+asyncpg://findesk:findesk@localhost:5433/findesk"
    app_redis_url: str = "redis://localhost:6380/0"
    recall_base_url: str = "http://localhost:8000"

    jwt_secret: str = "dev-only-secret"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 14

    # Redis streams / channels (shapes in contracts/events.md)
    jobs_stream_interactive: str = "agents:interactive"
    events_stream: str = "agents:events"
    events_consumer_group: str = "backend"
    run_channel_prefix: str = "run:"

    otel_service_name: str = "findesk-backend"


@lru_cache
def get_settings() -> Settings:
    return Settings()
