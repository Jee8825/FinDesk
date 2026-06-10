"""Smoke test the FastAPI app boots and exposes the contract (no datastores).

The lifespan's Neo4j init is best-effort, so the app starts even with no
services running; ``/health`` and the OpenAPI schema must be available.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from recall.api.app import app


def test_health_and_openapi():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}

        schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        for expected in [
            "/memory/ingest",
            "/memory/retrieve",
            "/memory/{memory_id}/why",
            "/memory/promote",
            "/memory/prefetch",
            "/admin/consolidate",
            "/conflicts",
            "/stats",
        ]:
            assert expected in paths, f"missing route {expected}"
