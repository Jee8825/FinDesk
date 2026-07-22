"""Pending-entry adoption + dead-letter routing — the at-least-once repair path."""

import asyncio
from types import SimpleNamespace

from findesk_agents.worker import reclaim_pending

SETTINGS = SimpleNamespace(
    jobs_stream_interactive="agents:interactive",
    jobs_consumer_group="workers",
    jobs_dead_stream="agents:dead",
    events_stream="agents:events",
    worker_consumer_name="worker-main",
    worker_max_deliveries=3,
    worker_reclaim_idle_ms=60_000,
)


class FakeRedis:
    """Just enough of the stream surface for reclaim_pending."""

    def __init__(self, pending):
        self._pending = pending  # list of dicts: message_id, times_delivered, msg
        self.added = []  # (stream, fields)
        self.acked = []

    async def xpending_range(self, stream, group, min, max, count, idle):  # noqa: A002
        return [
            {"message_id": p["message_id"], "times_delivered": p["times_delivered"]}
            for p in self._pending
        ]

    async def xclaim(self, stream, group, consumer, min_idle_time, message_ids):
        return [
            (p["message_id"], p["msg"])
            for p in self._pending
            if p["message_id"] in message_ids
        ]

    async def xadd(self, stream, fields):
        self.added.append((stream, fields))

    async def xack(self, stream, group, entry_id):
        self.acked.append(entry_id)


def _msg(run="r1"):
    return {"event": "job.ping.requested@v1", "run_id": run, "tenant_id": "t1", "payload": "{}"}


def test_stale_entry_below_limit_is_redispatched():
    redis = FakeRedis([{"message_id": "1-1", "times_delivered": 2, "msg": _msg()}])
    handled = []

    async def handler(r, msg, backend, memory):
        handled.append(msg["run_id"])

    counts = asyncio.run(
        reclaim_pending(redis, SETTINGS, backend=None, memory=None, handler=handler)
    )
    assert counts == {"retried": 1, "dead": 0}
    assert handled == ["r1"]
    assert redis.acked == ["1-1"]
    assert redis.added == []  # nothing dead-lettered


def test_poison_entry_dead_letters_fails_run_and_acks():
    redis = FakeRedis([{"message_id": "1-2", "times_delivered": 3, "msg": _msg("r2")}])

    async def handler(r, msg, backend, memory):  # pragma: no cover — must not run
        raise AssertionError("poison entry must not be re-dispatched")

    counts = asyncio.run(
        reclaim_pending(redis, SETTINGS, backend=None, memory=None, handler=handler)
    )
    assert counts == {"retried": 0, "dead": 1}
    streams = [s for s, _ in redis.added]
    # dead-letter copy with reason + run.done failed event, then acked off
    assert "agents:dead" in streams
    dead = next(f for s, f in redis.added if s == "agents:dead")
    assert dead["dead_reason"] == "exceeded 3 deliveries"
    assert dead["run_id"] == "r2"
    done = next(f for s, f in redis.added if s != "agents:dead")
    assert '"failed"' in done["payload"]
    assert redis.acked == ["1-2"]


def test_empty_pending_is_a_noop():
    redis = FakeRedis([])
    counts = asyncio.run(reclaim_pending(redis, SETTINGS, backend=None, memory=None))
    assert counts == {"retried": 0, "dead": 0}
    assert redis.acked == []
