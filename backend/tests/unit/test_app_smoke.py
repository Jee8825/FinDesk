from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_and_auth_guard():
    # lifespan not started: no redis/db needed for these paths
    app = create_app()
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}
    # protected route rejects anonymous access
    assert client.get("/api/v1/agent/runs").status_code == 401
    # unknown graph rejected before any infra is touched
    bad = client.post("/api/v1/agent/runs", json={"graph": "nope"})
    assert bad.status_code == 401  # auth first
