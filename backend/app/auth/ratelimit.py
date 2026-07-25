"""Redis fixed-window rate limiting + refresh-token revocation (B1).

Both ride the same Redis the job streams already require. Posture: outside
dev the limiter fails CLOSED (Redis down ⇒ auth attempts refused) — a
security control that silently disappears is worse than a brief outage;
in dev it fails open so a cold stack still logs in.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.config import get_settings
from app.events.streams import get_redis

log = logging.getLogger("findesk.auth")

LOGIN_LIMIT = 5  # attempts / window / (ip, email)
REFRESH_LIMIT = 30
WINDOW_S = 60

_REVOKED_PREFIX = "auth:revoked:"
_RL_PREFIX = "auth:rl:"


def remaining_ttl(exp_ts: int, *, now: datetime | None = None) -> int:
    """Seconds a revocation entry must outlive the token. Pure."""
    now_ts = int((now or datetime.now(UTC)).timestamp())
    return max(1, exp_ts - now_ts)


async def enforce_rate(scope: str, identity: str, *, limit: int) -> None:
    """Fixed window: INCR + EXPIRE. Raises 429 past the limit."""
    key = f"{_RL_PREFIX}{scope}:{identity}"
    try:
        r = get_redis()
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, WINDOW_S)
        if count > limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"too many {scope} attempts — retry in a minute",
            )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 — Redis unreachable
        if get_settings().app_env == "dev":
            log.warning("rate limiter skipped (redis unreachable, dev fail-open)")
            return
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "auth temporarily unavailable"
        ) from None


async def revoke_jti(jti: str, exp_ts: int) -> None:
    try:
        await get_redis().set(f"{_REVOKED_PREFIX}{jti}", "1", ex=remaining_ttl(exp_ts))
    except Exception:  # noqa: BLE001
        if get_settings().app_env != "dev":
            raise
        log.warning("revocation skipped (redis unreachable, dev fail-open)")


async def is_revoked(jti: str | None) -> bool:
    if not jti:
        return False  # pre-rotation token (no jti) — accepted until it expires
    try:
        return bool(await get_redis().exists(f"{_REVOKED_PREFIX}{jti}"))
    except Exception:  # noqa: BLE001
        if get_settings().app_env == "dev":
            log.warning("revocation check skipped (redis unreachable, dev fail-open)")
            return False
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "auth temporarily unavailable"
        ) from None
