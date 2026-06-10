#!/usr/bin/env python3
"""Seed dev data: demo tenant, owner login, and the Phase-1 synthetic SME —
clients/vendors, a bank account, and open invoices that pair with the fixture
statement at scripts/fixtures/statement_apr2026.csv. Idempotent.

Expected reconciliation of the fixture: 16 transactions inserted, 8 matched &
posted (7 by name, 1 by unique amount), 8 exceptions (1 ambiguous ₹60,000
credit + 7 debits, which v0 doesn't match).

Usage: .venv/bin/python scripts/seed_dev_data.py  (DB must be up: `make up`)
Login: founder@demo.findesk.in / demo1234
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from datetime import UTC, datetime, timedelta  # noqa: E402

from findesk_shared import uuid7  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.db import dispose_engine, session_scope  # noqa: E402
from app.db.models import (  # noqa: E402
    BankAccount,
    ChartAccount,
    Counterparty,
    Invoice,
    Membership,
    Tenant,
    User,
)
from app.db.repositories import UserRepo  # noqa: E402

DEMO_EMAIL = "founder@demo.findesk.in"
DEMO_PASSWORD = "demo1234"  # dev fixture only — no real data ever in seeds
DEMO_TENANT = "Demo Trading Co"

CLIENTS = [
    "Blue Tokai Coffee Pvt Ltd",
    "Origin Roasters Pvt Ltd",
    "Chai Point Retail",
    "Subko Specialty",
    "Araku Coffee Works",
    "Third Wave Brews",
    "KCRoasters Mumbai",
    "Devans South Traders",
]
VENDORS = ["AWS India", "WeWork BKC"]

# (client, number, amount_paise, issue_date) — due = issue + 30d.
# Amounts pair with scripts/fixtures/statement_apr2026.csv (see module docstring).
INVOICES = [
    ("Blue Tokai Coffee Pvt Ltd", "INV-2026-041", 4_500_000, "2026-03-05"),
    ("Origin Roasters Pvt Ltd", "INV-2026-042", 11_800_000, "2026-03-08"),
    ("Chai Point Retail", "INV-2026-043", 7_250_000, "2026-03-12"),
    ("Subko Specialty", "INV-2026-044", 23_600_000, "2026-03-15"),
    ("Araku Coffee Works", "INV-2026-045", 5_400_000, "2026-03-18"),
    ("Third Wave Brews", "INV-2026-046", 8_850_000, "2026-03-20"),
    ("KCRoasters Mumbai", "INV-2026-047", 11_200_000, "2026-03-22"),
    ("Devans South Traders", "INV-2026-048", 3_975_000, "2026-03-25"),
    # the two below share an amount: an ambiguous ₹60,000 credit must NOT auto-match
    ("Blue Tokai Coffee Pvt Ltd", "INV-2026-049", 6_000_000, "2026-03-26"),
    ("Origin Roasters Pvt Ltd", "INV-2026-050", 6_000_000, "2026-03-27"),
    # unpaid — stay open after the fixture reconciles
    ("Chai Point Retail", "INV-2026-051", 9_500_000, "2026-03-28"),
    ("Subko Specialty", "INV-2026-052", 15_000_000, "2026-03-30"),
]

# Phase-2 TDS hero case: ₹45,000 invoice paid as ₹44,100 (2% TDS) in the May
# fixture (statement_may2026.csv) → tds_adjusted proposal → approval queue.
# Phase-2b drift case: ₹2,00,000 invoice paid as ₹1,90,000 (5% TDS) in the
# June fixture — contradicts the remembered 2% pattern → memory conflict card.
LATE_INVOICES = [
    ("Blue Tokai Coffee Pvt Ltd", "INV-2026-053", 4_500_000, "2026-04-25"),
    ("Blue Tokai Coffee Pvt Ltd", "INV-2026-054", 20_000_000, "2026-05-20"),
]


async def ensure_identity(session) -> str:
    users = UserRepo(session)
    existing = await users.by_email(DEMO_EMAIL)
    if existing is not None:
        memberships = await users.memberships(existing.id)
        return memberships[0].tenant_id
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
    return tenant.id


async def ensure_books(session, tenant_id: str) -> None:
    count = await session.scalar(
        select(func.count()).select_from(Counterparty).where(Counterparty.tenant_id == tenant_id)
    )
    if count:
        print(f"books seed already present ({count} counterparties)")
        return
    session.add(
        BankAccount(
            id=uuid7(),
            tenant_id=tenant_id,
            bank="Demo Bank",
            account_ref="XX1234",
            source="upload",
        )
    )
    party_ids: dict[str, str] = {}
    for name in CLIENTS:
        pid = uuid7()
        party_ids[name] = pid
        session.add(
            Counterparty(
                id=pid,
                tenant_id=tenant_id,
                kind="client",
                name=name,
                contacts={"emails": [_demo_email(name)]},
            )
        )
    for name in VENDORS:
        session.add(Counterparty(id=uuid7(), tenant_id=tenant_id, kind="vendor", name=name))
    await session.flush()
    for client, number, amount_paise, issue in INVOICES:
        issue_dt = datetime.fromisoformat(issue).replace(tzinfo=UTC)
        session.add(
            Invoice(
                id=uuid7(),
                tenant_id=tenant_id,
                counterparty_id=party_ids[client],
                number=number,
                issue_date=issue_dt,
                due_date=issue_dt + timedelta(days=30),
                amount_paise=amount_paise,
                status="open",
            )
        )
    print(f"seeded {len(CLIENTS) + len(VENDORS)} counterparties, {len(INVOICES)} open invoices")


# Standard small-business expense chart (subset; grows with Phase 3 GST work)
CHART_OF_ACCOUNTS = [
    ("software_cloud", "Software & Cloud Services", "expense"),
    ("payroll", "Salaries & Payroll", "expense"),
    ("rent", "Rent & Workspace", "expense"),
    ("utilities", "Utilities & Electricity", "expense"),
    ("taxes_gst", "GST Payments", "expense"),
    ("taxes_tds", "TDS Deposits", "expense"),
    ("staff_welfare", "Staff Welfare & Meals", "expense"),
    ("travel", "Travel & Conveyance", "expense"),
    ("professional_fees", "Professional Fees", "expense"),
    ("bank_charges", "Bank Charges", "expense"),
    ("marketing", "Marketing & Ads", "expense"),
    ("misc_expense", "Miscellaneous Expense", "expense"),
]


def _demo_email(name: str) -> str:
    slug = "".join(c for c in name.lower() if c.isalnum() or c == " ").split()
    return f"accounts@{'-'.join(slug[:2])}.demo.findesk.in"


async def ensure_contacts(session, tenant_id: str) -> None:
    """Backfill contact emails on counterparties seeded before Phase 3b."""
    updated = 0
    for c in await session.scalars(
        select(Counterparty).where(
            Counterparty.tenant_id == tenant_id, Counterparty.kind == "client"
        )
    ):
        if not (c.contacts or {}).get("emails"):
            c.contacts = {"emails": [_demo_email(c.name)]}
            updated += 1
    if updated:
        print(f"backfilled contact emails on {updated} clients")


async def ensure_chart(session, tenant_id: str) -> None:
    count = await session.scalar(
        select(func.count()).select_from(ChartAccount).where(ChartAccount.tenant_id == tenant_id)
    )
    if count:
        return
    for code, name, type_ in CHART_OF_ACCOUNTS:
        session.add(
            ChartAccount(id=uuid7(), tenant_id=tenant_id, code=code, name=name, type=type_)
        )
    print(f"seeded {len(CHART_OF_ACCOUNTS)} chart-of-accounts entries")


async def ensure_late_invoices(session, tenant_id: str) -> None:
    """Idempotently add invoices introduced after the initial books seed."""
    parties = {
        c.name: c.id
        for c in (
            await session.scalars(
                select(Counterparty).where(Counterparty.tenant_id == tenant_id)
            )
        )
    }
    for client, number, amount_paise, issue in LATE_INVOICES:
        exists = await session.scalar(
            select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.number == number)
        )
        if exists is not None or client not in parties:
            continue
        issue_dt = datetime.fromisoformat(issue).replace(tzinfo=UTC)
        session.add(
            Invoice(
                id=uuid7(),
                tenant_id=tenant_id,
                counterparty_id=parties[client],
                number=number,
                issue_date=issue_dt,
                due_date=issue_dt + timedelta(days=30),
                amount_paise=amount_paise,
                status="open",
            )
        )
        print(f"seeded late invoice {number}")


async def main() -> None:
    async with session_scope() as session:
        tenant_id = await ensure_identity(session)
        await session.flush()
        await ensure_books(session, tenant_id)
        await session.flush()
        await ensure_late_invoices(session, tenant_id)
        await ensure_chart(session, tenant_id)
        await ensure_contacts(session, tenant_id)
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
