"""Request-scoped auth context: (user_id, tenant_id, role) from the JWT."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status

from app.auth.security import decode_token


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    tenant_id: str
    role: str


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return token


def get_auth(request: Request) -> AuthContext:
    try:
        payload = decode_token(_bearer_token(request), expected="access")
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc
    return AuthContext(
        user_id=payload["sub"], tenant_id=payload["ten"], role=payload["role"]
    )


Auth = Annotated[AuthContext, Depends(get_auth)]
