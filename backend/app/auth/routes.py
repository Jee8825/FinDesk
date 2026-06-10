"""Auth endpoints: login, refresh, me, tenant switch (contracts/api.yaml)."""

from __future__ import annotations

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.auth.deps import Auth
from app.auth.security import decode_token, mint_token, verify_password
from app.db import session_scope
from app.db.repositories import TenantRepo, UserRepo

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    tenant_id: str
    role: str


class MembershipOut(BaseModel):
    tenant_id: str
    tenant_name: str
    role: str


class MeOut(BaseModel):
    user_id: str
    email: str
    active_tenant_id: str
    role: str
    memberships: list[MembershipOut]


def _pair(user_id: str, tenant_id: str, role: str) -> TokenPair:
    return TokenPair(
        access_token=mint_token(user_id=user_id, tenant_id=tenant_id, role=role, kind="access"),
        refresh_token=mint_token(user_id=user_id, tenant_id=tenant_id, role=role, kind="refresh"),
        tenant_id=tenant_id,
        role=role,
    )


@router.post("/auth/login", response_model=TokenPair)
async def login(body: LoginRequest) -> TokenPair:
    async with session_scope() as session:
        users = UserRepo(session)
        user = await users.by_email(body.email.lower())
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
        memberships = await users.memberships(user.id)
        if not memberships:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "no tenant membership")
        active = memberships[0]
        return _pair(user.id, active.tenant_id, active.role)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest) -> TokenPair:
    try:
        payload = decode_token(body.refresh_token, expected="refresh")
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token") from exc
    return _pair(payload["sub"], payload["ten"], payload["role"])


@router.get("/me", response_model=MeOut)
async def me(auth: Auth) -> MeOut:
    async with session_scope() as session:
        users = UserRepo(session)
        tenants = TenantRepo(session)
        user = await users.by_id(auth.user_id)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
        memberships = []
        for m in await users.memberships(user.id):
            tenant = await tenants.by_id(m.tenant_id)
            memberships.append(
                MembershipOut(
                    tenant_id=m.tenant_id,
                    tenant_name=tenant.name if tenant else "?",
                    role=m.role,
                )
            )
        return MeOut(
            user_id=user.id,
            email=user.email,
            active_tenant_id=auth.tenant_id,
            role=auth.role,
            memberships=memberships,
        )


@router.post("/tenants/{tenant_id}/switch", response_model=TokenPair)
async def switch_tenant(tenant_id: str, auth: Auth) -> TokenPair:
    async with session_scope() as session:
        membership = await UserRepo(session).membership(auth.user_id, tenant_id)
        if membership is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of that tenant")
        return _pair(auth.user_id, tenant_id, membership.role)
