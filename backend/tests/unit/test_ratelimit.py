"""B1 pure bits — revocation TTL math (the Redis paths are integration-tier)."""

from datetime import UTC, datetime

from app.auth.ratelimit import remaining_ttl


def test_remaining_ttl_tracks_token_expiry():
    now = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)
    exp = int(datetime(2026, 7, 23, 12, 10, 0, tzinfo=UTC).timestamp())
    assert remaining_ttl(exp, now=now) == 600


def test_remaining_ttl_never_below_one_second():
    now = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)
    expired = int(datetime(2026, 7, 23, 11, 0, 0, tzinfo=UTC).timestamp())
    assert remaining_ttl(expired, now=now) == 1
