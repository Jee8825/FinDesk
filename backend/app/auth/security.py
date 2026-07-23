"""Password hashing (argon2) and JWT minting/verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.config import get_settings

_hasher = PasswordHasher()
ALGORITHM = "HS256"

TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerificationError:
        return False


def mint_token(*, user_id: str, tenant_id: str, role: str, kind: TokenType) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    ttl = (
        timedelta(seconds=settings.access_token_ttl_seconds)
        if kind == "access"
        else timedelta(days=settings.refresh_token_ttl_days)
    )
    from findesk_shared import uuid7

    payload = {
        "sub": user_id,
        "ten": tenant_id,
        "role": role,
        "typ": kind,
        "jti": uuid7(),  # refresh rotation/revocation handle (B1)
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, *, expected: TokenType) -> dict[str, Any]:
    """Raises jwt.PyJWTError on anything invalid; callers map to 401."""
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    if payload.get("typ") != expected:
        raise jwt.InvalidTokenError(f"expected {expected} token")
    return payload
