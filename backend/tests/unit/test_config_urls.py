"""Connection-string normalization — deployment portability.

Managed Postgres providers hand out a plain URL; this app runs an async engine.
Getting this wrong does not fail a test, it fails a deploy at boot, so the
shapes each provider actually emits are pinned here.
"""

from __future__ import annotations

import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "given",
    [
        "postgres://u:p@h:5432/db",       # Heroku / older Render
        "postgresql://u:p@h:5432/db",     # Render / Neon / Supabase
    ],
)
def test_plain_urls_get_the_async_driver(given, monkeypatch):
    monkeypatch.setenv("APP_DATABASE_URL", given)
    assert Settings().app_database_url.startswith("postgresql+asyncpg://")
    assert Settings().app_database_url.endswith("u:p@h:5432/db")


def test_an_explicit_driver_is_left_alone(monkeypatch):
    url = "postgresql+asyncpg://u:p@h:5432/db"
    monkeypatch.setenv("APP_DATABASE_URL", url)
    assert Settings().app_database_url == url


def test_query_parameters_survive(monkeypatch):
    """Managed providers append sslmode and friends."""
    monkeypatch.setenv("APP_DATABASE_URL", "postgresql://u:p@h/db?sslmode=require")
    assert Settings().app_database_url == "postgresql+asyncpg://u:p@h/db?sslmode=require"
