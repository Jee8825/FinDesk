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
    counts = {"parties_created": 0, "unclassified_vendors": 0, "status_conflicts": 0}

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
            row.number: row
            for row in await session.scalars(
                select(model).where(model.tenant_id == tenant_id)
            )
        }
        created = updated = skipped = 0
        for ref in result.bills:
            row = existing.get(ref.external_ref)
            if row is not None:
                # Re-pull = refresh, with one hard rule: "paid" is terminal
                # here. Local recon marked it from bank evidence; a stale
                # export saying otherwise is a disagreement to surface, never
                # a silent resurrection (the product's conflict ethos).
                if row.status == "paid" and ref.outstanding_paise > 0:
                    counts["status_conflicts"] += 1
                    skipped += 1
                    continue
                settled = ref.outstanding_paise == 0
                changed = False
                if side == "payables" and row.outstanding_paise != ref.outstanding_paise:
                    row.outstanding_paise = ref.outstanding_paise
                    changed = True
                if settled and row.status != "paid":
                    row.status = "paid"
                    changed = True
                updated += int(changed)
                skipped += int(not changed)
                continue
            if ref.outstanding_paise == 0:
                skipped += 1  # settled and previously unknown — nothing to book
                continue
            party = await ensure_party(ref.party, kind)
            if kind == "vendor" and not party.msme_status:
                counts["unclassified_vendors"] += 1
            fields: dict[str, Any] = dict(
                id=uuid7(),
                tenant_id=tenant_id,
                counterparty_id=party.id,
                number=ref.external_ref,
                issue_date=ref.bill_date,
                due_date=ref.due_date or ref.bill_date + timedelta(days=30),
                acceptance_date=ref.bill_date,
                status="open",
            )
            if side == "payables":
                fields |= {
                    "amount_paise": ref.amount_paise,
                    "outstanding_paise": ref.outstanding_paise,
                }
            else:
                # Invoice has no outstanding column — the unpaid portion is the
                # actionable amount for radar/forecast, so it becomes the amount
                fields |= {"amount_paise": ref.outstanding_paise}
            obj = model(**fields)
            session.add(obj)
            existing[ref.external_ref] = obj  # duplicate refs in one pull hit update path
            created += 1
        return {"created": created, "updated": updated, "skipped": skipped}

    inv = await upsert("receivables", receivables)
    pay = await upsert("payables", payables)
    return {
        "invoices_created": inv["created"],
        "invoices_updated": inv["updated"],
        "invoices_skipped": inv["skipped"],
        "bills_created": pay["created"],
        "bills_updated": pay["updated"],
        "bills_skipped": pay["skipped"],
        **counts,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
