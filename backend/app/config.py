"""App settings — env-driven, never read os.environ elsewhere."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_database_url: str = "postgresql+asyncpg://findesk:findesk@localhost:5433/findesk"
    app_redis_url: str = "redis://localhost:6380/0"
    recall_base_url: str = "http://localhost:8000"

    app_env: str = "dev"  # dev | staging | prod
    # 32+ chars even in dev (HS256 minimum); MUST be overridden outside dev
    jwt_secret: str = "dev-only-secret-not-for-production!!"
    internal_api_token: str = "dev-internal-token"  # worker ↔ backend internal API
    upload_dir: str = "var/uploads"  # dev only; object storage in staging/prod
    outbox_dir: str = "var/outbox"  # sandbox email delivery (dev/staging)
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 14

    # Redis streams / channels (shapes in contracts/events.md)
    jobs_stream_interactive: str = "agents:interactive"
    jobs_consumer_group: str = "workers"  # must mirror agents config
    events_stream: str = "agents:events"
    events_consumer_group: str = "backend"
    run_channel_prefix: str = "run:"

    otel_service_name: str = "findesk-backend"

    # RBI bank rate in bps — §16 interest = 3× this. Re-verify against
    # rbi.org.in after every MPC revision; override here per deployment
    # (services/statutory.py documents the protocol).
    statutory_bank_rate_bps: int = 675

    # TallyPrime HTTP-XML gateway (tools/tally). "fixture" exercises the real
    # connector against checked-in gateway XML (clearly labelled in responses);
    # "live" posts to tally_gateway_url — point it at a running TallyPrime.
    tally_mode: str = "fixture"  # fixture | live
    tally_gateway_url: str = "http://localhost:9000"
    tally_company: str | None = None

    # GST IMS (tools/ims). "fixture" replays checked-in records through the
    # real match/approve loop; "live" needs a GSP adapter (roadmap) and
    # refuses to construct until one exists.
    ims_mode: str = "fixture"  # fixture | live
    ims_actions_dir: str = "var/ims"  # sandbox set_state receipts


    @field_validator("app_database_url")
    @classmethod
    def _async_driver(cls, value: str) -> str:
        """Accept the plain URL every managed Postgres hands out.

        Render, Neon, Supabase and Heroku all emit `postgres://` or
        `postgresql://`, but this app runs an async engine and needs the
        `+asyncpg` driver. Rewriting here rather than asking every deployment to
        hand-edit its own connection string — and it keeps alembic and the
        engine in agreement, since both read this one setting.
        """
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


def assert_safe_settings() -> None:
    """Refuse to boot non-dev environments on dev credentials (fail-fast)."""
    s = get_settings()
    if s.app_env == "dev":
        return
    problems = []
    if "dev-only" in s.jwt_secret or len(s.jwt_secret) < 32:
        problems.append("JWT_SECRET is a dev default or shorter than 32 chars")
    if "dev-internal" in s.internal_api_token or len(s.internal_api_token) < 32:
        problems.append("INTERNAL_API_TOKEN is a dev default or shorter than 32 chars")
    if problems:
        raise RuntimeError(f"unsafe settings for APP_ENV={s.app_env}: " + "; ".join(problems))
