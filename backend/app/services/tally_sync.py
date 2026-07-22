"""Tally pull-through — gateway bills/receivables into the tenant's books.

Runs the real connector (envelopes → flat-sibling parser → normalization) in
either mode; "fixture" serves checked-in gateway XML and is labelled as such
in every response, because demo data must never masquerade as a live pull.

Idempotent by document number per side — re-pulling never duplicates. Vendors
arrive without MSME status (Tally does not carry Udyam registration): they
surface as unclassified and the payables shield excludes them until a human
tags them — a §43B(h) determination is a human/CA call, not an inference.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from findesk_shared import uuid7
from findesk_tools.tally import BillsResult, TallyGateway, fixture_transport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Bill, Counterparty, Invoice

Side = Literal["receivables", "payables"]


def build_gateway() -> tuple[TallyGateway, str]:
    """Gateway per settings → (gateway, mode-label)."""
    s = get_settings()
    if s.tally_mode == "live":
        return TallyGateway(s.tally_gateway_url, company=s.tally_company), "live"
    return (
        TallyGateway(s.tally_gateway_url, company=s.tally_company, transport=fixture_transport),
        "fixture",
    )


async def sync_books(
    session: AsyncSession,
    tenant_id: str,
    *,
    receivables: BillsResult,
    payables: BillsResult,
) -> dict[str, Any]:
    """Upsert parties + invoices + bills from normalized gateway results."""
    parties = {
        c.name.lower(): c
        for c in await session.scalars(
            select(Counterparty).where(Counterparty.tenant_id == tenant_id)
        )
    }
    counts = {"parties_created": 0, "unclassified_vendors": 0}

    async def ensure_party(name: str, kind: str) -> Counterparty:
        party = parties.get(name.lower())
        if party is None:
            party = Counterparty(
                id=uuid7(), tenant_id=tenant_id, kind=kind, name=name, contacts={}
            )
            session.add(party)
            # flush immediately so same-flush FK ordering can never bite the
            # child rows that reference this party
            await session.flush()
            parties[name.lower()] = party
            counts["parties_created"] += 1
        return party

    async def upsert(side: Side, result: BillsResult) -> dict[str, int]:
        model = Invoice if side == "receivables" else Bill
        kind = "client" if side == "receivables" else "vendor"
        existing = {
            row.number
            for row in await session.scalars(
                select(model).where(model.tenant_id == tenant_id)
            )
        }
        created = skipped = 0
        for ref in result.bills:
            if ref.external_ref in existing:
                skipped += 1
                continue
            party = await ensure_party(ref.party, kind)
            if kind == "vendor" and not party.msme_status:
                counts["unclassified_vendors"] += 1
            session.add(
                model(
                    id=uuid7(),
                    tenant_id=tenant_id,
                    counterparty_id=party.id,
                    number=ref.external_ref,
                    issue_date=ref.bill_date,
                    due_date=ref.due_date or ref.bill_date + timedelta(days=30),
                    acceptance_date=ref.bill_date,
                    amount_paise=ref.outstanding_paise or ref.amount_paise,
                    status="open",
                )
            )
            existing.add(ref.external_ref)
            created += 1
        return {"created": created, "skipped": skipped}

    inv = await upsert("receivables", receivables)
    pay = await upsert("payables", payables)
    return {
        "invoices_created": inv["created"],
        "invoices_skipped": inv["skipped"],
        "bills_created": pay["created"],
        "bills_skipped": pay["skipped"],
        **counts,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
