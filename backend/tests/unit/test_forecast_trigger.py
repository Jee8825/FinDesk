"""Forecast trigger — debounce and enqueue-after-commit ordering (repos faked)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from app.services import forecast_trigger


class _FakeRuns:
    def __init__(self, active: bool) -> None:
        self.active = active
        self.added: list[Any] = []

    async def active_run(self, tenant_id: str, graph: str):
        return object() if self.active else None

    async def add(self, run) -> None:
        self.added.append(run)


def _wire(monkeypatch, *, active: bool):
    runs = _FakeRuns(active)
    events: list[tuple[str, str, str]] = []
    committed: list[bool] = []

    @asynccontextmanager
    async def fake_scope():
        yield object()
        committed.append(True)  # context exit == transaction commit

    async def fake_enqueue(event: str, tenant_id: str, run_id: str, payload: dict) -> None:
        assert committed, "job must be enqueued only after the run row commits"
        events.append((event, tenant_id, run_id))

    monkeypatch.setattr(forecast_trigger, "session_scope", fake_scope)
    monkeypatch.setattr(forecast_trigger, "RunRepo", lambda session: runs)
    monkeypatch.setattr(forecast_trigger, "enqueue_job", fake_enqueue)
    return runs, events


async def test_trigger_enqueues_one_forecast_run(monkeypatch):
    runs, events = _wire(monkeypatch, active=False)
    run_id = await forecast_trigger.trigger_forecast_recompute(
        tenant_id="t1", requested_by="u1"
    )
    assert run_id is not None
    assert len(runs.added) == 1
    assert runs.added[0].graph == "cash_forecast"
    assert events == [("job.cash_forecast.requested@v1", "t1", run_id)]


async def test_trigger_debounces_when_run_already_active(monkeypatch):
    runs, events = _wire(monkeypatch, active=True)
    run_id = await forecast_trigger.trigger_forecast_recompute(
        tenant_id="t1", requested_by="u1"
    )
    assert run_id is None
    assert runs.added == []
    assert events == []
