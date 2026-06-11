"""Integration fixtures: real Postgres via testcontainers, migrated to head.

Marked ``integration`` — excluded from the unit run; `make test-int` or the
nightly workflow runs them. Each test function gets a clean database.
"""

from __future__ import annotations

import os

import pytest
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def pg_url() -> str:
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        yield url


@pytest.fixture
async def db(pg_url, monkeypatch):
    """Fresh schema per test: env → settings → migrate → yield → dispose."""
    monkeypatch.setenv("APP_DATABASE_URL", pg_url)

    from app import config
    from app import db as appdb

    config.get_settings.cache_clear()
    await appdb.dispose_engine()

    import asyncio

    from alembic import command
    from alembic.config import Config as AlembicConfig

    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    cfg = AlembicConfig(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend_dir, "app", "db", "migrations"))
    # alembic's async env calls asyncio.run(); run it off this event loop
    await asyncio.to_thread(command.downgrade, cfg, "base")
    await asyncio.to_thread(command.upgrade, cfg, "head")

    yield appdb

    await appdb.dispose_engine()
    config.get_settings.cache_clear()


@pytest.fixture
async def seeded(db):
    """Two tenants with an owner, a client, an open invoice and a credit txn each."""
    from datetime import UTC, datetime

    from findesk_shared import uuid7

    from app.auth.security import hash_password
    from app.db import session_scope
    from app.db.models import (
        BankAccount,
        BankTransaction,
        Counterparty,
        Invoice,
        Membership,
        Tenant,
        User,
    )

    out = {}
    async with session_scope() as session:
        for label in ("a", "b"):
            tenant = Tenant(id=uuid7(), name=f"Tenant {label.upper()}")
            user = User(
                id=uuid7(), email=f"owner-{label}@t.in", password_hash=hash_password("pw")
            )
            session.add_all([tenant, user])
            await session.flush()
            session.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
            party = Counterparty(
                id=uuid7(), tenant_id=tenant.id, kind="client", name=f"Client {label.upper()}"
            )
            account = BankAccount(
                id=uuid7(), tenant_id=tenant.id, bank="T Bank", account_ref="XX"
            )
            session.add_all([party, account])
            await session.flush()
            invoice = Invoice(
                id=uuid7(),
                tenant_id=tenant.id,
                counterparty_id=party.id,
                number=f"INV-{label.upper()}-1",
                issue_date=datetime(2026, 5, 1, tzinfo=UTC),
                due_date=datetime(2026, 5, 31, tzinfo=UTC),
                amount_paise=1_000_000,
                status="open",
            )
            txn = BankTransaction(
                id=uuid7(),
                tenant_id=tenant.id,
                bank_account_id=account.id,
                external_ref=f"R-{label}",
                value_date=datetime(2026, 6, 5, tzinfo=UTC),
                amount_paise=1_000_000,
                direction="cr",
                narration=f"NEFT-CLIENT {label.upper()}-PAY",
                dedupe_hash=f"hash-{label}",
                source={},
            )
            session.add_all([invoice, txn])
            out[label] = {
                "tenant_id": tenant.id,
                "user_id": user.id,
                "party_id": party.id,
                "invoice_id": invoice.id,
                "txn_id": txn.id,
            }
    return out
