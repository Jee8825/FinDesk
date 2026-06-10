"""All SQL for the backend lives here (hard rule #4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, AgentStep, Membership, Tenant, User


class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def by_id(self, user_id: str) -> User | None:
        return await self.session.get(User, user_id)

    async def memberships(self, user_id: str) -> list[Membership]:
        rows = await self.session.scalars(
            select(Membership).where(Membership.user_id == user_id)
        )
        return list(rows)

    async def membership(self, user_id: str, tenant_id: str) -> Membership | None:
        return await self.session.scalar(
            select(Membership).where(
                Membership.user_id == user_id, Membership.tenant_id == tenant_id
            )
        )

    async def add(self, user: User) -> None:
        self.session.add(user)


class TenantRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_id(self, tenant_id: str) -> Tenant | None:
        return await self.session.get(Tenant, tenant_id)

    async def add(self, tenant: Tenant) -> None:
        self.session.add(tenant)


class RunRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, run: AgentRun) -> None:
        self.session.add(run)

    async def by_id(self, run_id: str, tenant_id: str) -> AgentRun | None:
        return await self.session.scalar(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == tenant_id)
        )

    async def by_id_any_tenant(self, run_id: str) -> AgentRun | None:
        """Events-consumer path only — never expose through the API."""
        return await self.session.get(AgentRun, run_id)

    async def list_for_tenant(self, tenant_id: str, limit: int = 50) -> list[AgentRun]:
        rows = await self.session.scalars(
            select(AgentRun)
            .where(AgentRun.tenant_id == tenant_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return list(rows)

    async def set_status(
        self,
        run_id: str,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status}
        if started_at is not None:
            values["started_at"] = started_at
        if finished_at is not None:
            values["finished_at"] = finished_at
        await self.session.execute(
            update(AgentRun).where(AgentRun.id == run_id).values(**values)
        )

    async def steps(self, run_id: str) -> list[AgentStep]:
        rows = await self.session.scalars(
            select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.created_at)
        )
        return list(rows)

    async def upsert_step(
        self,
        *,
        run_id: str,
        tenant_id: str,
        step_id: str,
        name: str,
        status: str,
        detail: dict[str, Any],
    ) -> None:
        existing = await self.session.scalar(
            select(AgentStep).where(AgentStep.step_id == step_id)
        )
        if existing is None:
            self.session.add(
                AgentStep(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    step_id=step_id,
                    name=name,
                    status=status,
                    detail=detail,
                )
            )
        else:
            existing.status = status
            existing.detail = {**existing.detail, **detail}
