"""Service-URL normalization — deployment portability.

Render exposes an internal service as `host:port` with no scheme. httpx rejects
that at CLIENT CONSTRUCTION, so the worker would crash-loop on boot and read as
a broken image rather than a missing scheme.
"""

from __future__ import annotations

import pytest

from findesk_agents.config import Settings


@pytest.mark.parametrize("field", ["backend_base_url", "recall_base_url"])
def test_a_bare_hostport_gets_a_scheme(field, monkeypatch):
    monkeypatch.setenv(field.upper(), "findesk-api:8080")
    assert getattr(Settings(), field) == "http://findesk-api:8080"


@pytest.mark.parametrize("url", ["http://api:8080", "https://api.example.com"])
def test_an_explicit_scheme_is_left_alone(url, monkeypatch):
    monkeypatch.setenv("BACKEND_BASE_URL", url)
    assert Settings().backend_base_url == url


def test_an_empty_value_is_not_given_a_scheme(monkeypatch):
    """Empty means 'not configured' — turning it into http:// would mask that."""
    monkeypatch.setenv("RECALL_BASE_URL", "")
    assert Settings().recall_base_url == ""
