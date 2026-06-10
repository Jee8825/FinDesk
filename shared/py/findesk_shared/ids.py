"""UUIDv7 (RFC 9562) — time-ordered IDs, the repo-wide primary key type."""

from __future__ import annotations

import os
import time
import uuid

_last: tuple[int, int] = (0, 0)  # (unix_ms, counter) for same-ms monotonicity


def uuid7() -> str:
    """Return a UUIDv7 string: 48-bit unix ms, 12-bit counter, 62 random bits."""
    global _last
    unix_ms = time.time_ns() // 1_000_000
    last_ms, counter = _last
    if unix_ms == last_ms:
        counter = (counter + 1) & 0x0FFF
        if counter == 0:  # counter overflow within one ms: borrow the next ms
            unix_ms += 1
    else:
        counter = int.from_bytes(os.urandom(2), "big") & 0x07FF
    _last = (unix_ms, counter)

    rand = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (
        (unix_ms & ((1 << 48) - 1)) << 80
        | 0x7 << 76
        | counter << 64
        | 0b10 << 62
        | rand
    )
    return str(uuid.UUID(int=value))
