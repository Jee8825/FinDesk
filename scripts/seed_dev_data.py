#!/usr/bin/env python3
"""Seed dev data: demo tenant + owner login (Phase 0).

Grows into the full synthetic SME (vendors, clients, 6 months of transactions,
planted anomalies) in Phase 1. Idempotent — safe to re-run.

Usage: .venv/bin/python scripts/seed_dev_data.py  (DB must be up: `make up`)
Login: founder@demo.findesk.in / demo1234
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from findesk_shared import uuid7  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.db import dispose_engine, session_scope  # noqa: E402
from app.db.models import Membership, Tenant, User  # noqa: E402
from app.db.repositories import UserRepo  # noqa: E402

DEMO_EMAIL = "founder@demo.findesk.in"
DEMO_PASSWORD = "demo1234"  # dev fixture only — no real data ever in seeds
DEMO_TENANT = "Demo Trading Co"


async def main() -> None:
    async with session_scope() as session:
        users = UserRepo(session)
        existing = await users.by_email(DEMO_EMAIL)
        if existing is not None:
            print(f"seed already present: {DEMO_EMAIL}")
            return
        # ids assigned up front: column defaults only fire at flush, and the
        # membership row needs the FKs at construction time
        tenant = Tenant(id=uuid7(), name=DEMO_TENANT, plan="startup")
        user = User(id=uuid7(), email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        session.add_all([tenant, user])
        # no ORM relationships on purpose (repos own joins), so flush parents
        # first to guarantee FK order
        await session.flush()
        session.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
        print(f"seeded tenant {tenant.name!r} + owner {DEMO_EMAIL} / {DEMO_PASSWORD}")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
