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


# --- worker liveness: a busy worker is not a dead worker --------------------


def _live(consumer: dict) -> bool:
    """Mirror of the predicate in routes_agent.agent_health."""
    from app.api.routes_agent import WORKER_IDLE_THRESHOLD_MS

    return (
        int(consumer.get("idle", 1 << 62)) < WORKER_IDLE_THRESHOLD_MS
        or int(consumer.get("pending", 0)) > 0
    )


def test_a_recently_polling_worker_is_live():
    assert _live({"idle": 1_500, "pending": 0})


def test_a_worker_busy_inside_a_long_graph_is_live():
    """Regression: idle measures time since the last POLL, so a worker inside a
    30s+ graph is not polling and used to read as offline while working. A
    consumer holding pending entries is processing them by definition."""
    assert _live({"idle": 600_000, "pending": 1})


def test_a_silent_worker_with_no_work_is_not_live():
    assert not _live({"idle": 600_000, "pending": 0})


def test_a_missing_idle_field_is_not_live():
    """Absent data must fail closed — never claim liveness we cannot see."""
    assert not _live({})
