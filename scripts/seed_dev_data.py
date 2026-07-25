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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
# LeakRadar seeding parses a statement with the real tool and categorizes with
# the agents' own lexicon, so the seed can never disagree with a real run.
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "tools"))

from datetime import UTC, datetime, timedelta  # noqa: E402

from findesk_shared import uuid7  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.db import dispose_engine, session_scope  # noqa: E402
from app.db.models import (  # noqa: E402
    BankAccount,
    Bill,
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

# Buyer-side 43B(h) demo: registered-MSE vendors whose open bills run the §15
# clock against *us*. (name, msme_status)
MSE_VENDORS = [
    ("Sundaram Packaging", "micro"),
    ("Kaveri Print Works", "small"),
]

# (vendor, number, amount_paise, issue_date) — §15 clock runs from issue
# (acceptance defaults to issue). Dates crafted for the three bands:
# breached (>45d), closing (<7d left), within (fresh).
BILLS = [
    ("Sundaram Packaging", "PB-2026-889", 5_230_000, "2026-05-20"),  # breached
    ("Kaveri Print Works", "PB-2026-014", 2_140_000, "2026-06-10"),  # closing
    ("Sundaram Packaging", "PB-2026-902", 7_800_000, "2026-07-10"),  # within
    ("AWS India", "PB-2026-777", 1_650_000, "2026-07-01"),  # non-MSE — excluded
]

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
    # future-due: B3 scenario bands only spread for not-yet-due receivables
    ("Subko Specialty", "INV-2026-055", 40_000_000, "2026-06-05"),
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


SECOND_TENANT = "Meridian Textiles Co"


async def ensure_second_tenant(session) -> str | None:
    """A second client tenant on the same login — makes the CA roster and the
    explicit tenant-switch flow demoable (one CA, many clients)."""
    users = UserRepo(session)
    user = await users.by_email(DEMO_EMAIL)
    if user is None:
        return None
    memberships = await users.memberships(user.id)
    if len(memberships) > 1:
        return memberships[1].tenant_id
    tenant = Tenant(id=uuid7(), name=SECOND_TENANT, plan="startup")
    session.add(tenant)
    await session.flush()
    session.add(Membership(user_id=user.id, tenant_id=tenant.id, role="ca"))
    print(f"seeded second tenant {SECOND_TENANT!r} (role ca) for {DEMO_EMAIL}")
    return tenant.id


# --------------------------------------------------------------- LeakRadar
# Two dedicated tenants so LeakRadar demos on CLEAN data. The main demo tenant
# carries invoices, bills, IMS records and its own statements; dropping 75 more
# debits into it drags AWS from monthly to irregular and pushes older
# transactions out of the command palette's first page. Separate tenants also
# make dual-mode demoable side by side, which is the point of having two modes.

LEAK_TENANTS = (
    ("LeakRadar Demo — Business", "business", "leakradar_business.csv", "XX7788"),
    ("LeakRadar Demo — Personal", "personal", "leakradar_personal.csv", "XX9911"),
)


async def ensure_leak_tenants(session) -> list[str]:
    """Idempotent: creates each tenant, its bank account, and its debits."""
    from findesk_tools.bank_statements import parse_statement

    from app.db.models import BankTransaction

    users = UserRepo(session)
    user = await users.by_email(DEMO_EMAIL)
    if user is None:
        return []

    created: list[str] = []
    for name, mode, fixture, account_ref in LEAK_TENANTS:
        existing = await session.scalar(select(Tenant).where(Tenant.name == name))
        if existing is not None:
            print(f"leak tenant {name!r} already present")
            created.append(existing.id)
            continue

        path = ROOT / "scripts" / "fixtures" / fixture
        if not path.exists():
            print(f"!! missing {fixture} — run scripts/make_leak_fixtures.py")
            continue

        # parent first, then flush: a single add_all does not guarantee insert
        # order, so the bank account's FK to tenants can hit an absent row
        tenant = Tenant(id=uuid7(), name=name, plan="startup", leak_mode=mode)
        session.add(tenant)
        await session.flush()

        account = BankAccount(
            id=uuid7(),
            tenant_id=tenant.id,
            bank="Demo Bank",
            account_ref=account_ref,
            source="upload",
        )
        session.add_all(
            [account, Membership(user_id=user.id, tenant_id=tenant.id, role="owner")]
        )
        await session.flush()

        result = parse_statement(path.read_text(encoding="utf-8"))
        rows = 0
        for txn in result.transactions:
            if txn.direction != "dr":
                continue
            session.add(
                BankTransaction(
                    id=uuid7(),
                    tenant_id=tenant.id,
                    bank_account_id=account.id,
                    external_ref=txn.external_ref,
                    value_date=txn.value_date,
                    amount_paise=txn.amount_paise,
                    direction="dr",
                    narration=txn.narration,
                    counterparty_hint=txn.counterparty_hint,
                    dedupe_hash=txn.dedupe_hash(),
                    source={"kind": "bank_statement", "external_id": fixture},
                    category_code=_leak_category(txn.narration),
                    category_source="rule",
                )
            )
            rows += 1
        await session.flush()
        print(f"seeded {name!r} ({mode}) — {rows} debits from {fixture}")
        created.append(tenant.id)
    return created


def _leak_category(narration: str) -> str | None:
    """Categorize at seed time using the agents' own lexicon.

    Imported through the real categorizer rather than a copy, so the seed can
    never disagree with what a reconciliation run would assign.
    """
    from findesk_agents.graphs.reconciliation.categorization import LEXICON

    for pattern, code, _confidence in LEXICON:
        if pattern.search(narration):
            return code
    return None


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


async def ensure_bills(session, tenant_id: str) -> None:
    """Idempotently add MSE vendors + open payable bills (43B(h) demo)."""
    parties = {
        c.name: c
        for c in (
            await session.scalars(
                select(Counterparty).where(Counterparty.tenant_id == tenant_id)
            )
        )
    }
    for name, msme_status in MSE_VENDORS:
        if name in parties:
            if parties[name].msme_status != msme_status:
                parties[name].msme_status = msme_status
            continue
        vendor = Counterparty(
            id=uuid7(), tenant_id=tenant_id, kind="vendor", name=name, msme_status=msme_status
        )
        session.add(vendor)
        parties[name] = vendor
    await session.flush()
    for vendor_name, number, amount_paise, issue in BILLS:
        exists = await session.scalar(
            select(Bill).where(Bill.tenant_id == tenant_id, Bill.number == number)
        )
        if exists is not None or vendor_name not in parties:
            continue
        issue_dt = datetime.fromisoformat(issue).replace(tzinfo=UTC)
        session.add(
            Bill(
                id=uuid7(),
                tenant_id=tenant_id,
                counterparty_id=parties[vendor_name].id,
                number=number,
                issue_date=issue_dt,
                due_date=issue_dt + timedelta(days=45),
                amount_paise=amount_paise,
                outstanding_paise=amount_paise,
                status="open",
            )
        )
        print(f"seeded bill {number}")


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
        await ensure_bills(session, tenant_id)
        await ensure_chart(session, tenant_id)
        await ensure_contacts(session, tenant_id)
        second_id = await ensure_second_tenant(session)
        if second_id:
            await session.flush()
            await ensure_chart(session, second_id)  # empty books, real chart
        for leak_id in await ensure_leak_tenants(session):
            await ensure_chart(session, leak_id)
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
