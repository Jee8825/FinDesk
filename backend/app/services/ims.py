"""GST IMS queue — sync, deterministic match, recommendation, gated actions.

Since 1 Apr 2026 acting on the Invoice Management System decides input-tax
credit (amended Section 38). FinDesk's posture: the *match* and the
*recommendation* are deterministic code over the purchase register the books
already hold (Tally sync + imports); the *action* (accept/reject) only ever
executes inside decide_approval with a minted token — same maker–checker
surface as email sends and TReDS listings.

Sync follows the lap-2 rule: a decided state is terminal — re-pulls refresh
pending rows only and never resurrect or flip a human decision.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Bill, Counterparty, ImsRecord
from app.services import statutory
from app.services.audit import write_audit

# Amount agreement thresholds for the tolerant tier: rounding-level deltas
# (freight rounding, paise truncation) shouldn't force a human review.
TOLERANCE_PAISE = 10_000  # ₹100 absolute …
TOLERANCE_BPS = 25  # … or 0.25% of the bill, whichever is larger

CA_NOTE = (
    "Recommendations are deterministic 3-way checks against your purchase "
    "register. Accept/reject executes only after maker–checker approval; "
    "confirm period cut-offs with your CA before GSTR-3B."
)


def get_provider(settings: Settings):
    """Fixture provider today; a GSP adapter (live mode) is roadmap."""
    if settings.ims_mode == "live":
        raise NotImplementedError(
            "IMS live mode needs a GSP adapter (Adaequare-class) — roadmap; "
            "run ims_mode=fixture"
        )
    from findesk_tools.ims import SandboxImsProvider

    return SandboxImsProvider(settings.ims_actions_dir)


# --------------------------------------------------------------- pure core


@dataclass(frozen=True)
class BillLite:
    number: str
    amount_paise: int
    outstanding_paise: int
    status: str  # open|paid
    vendor: str


@dataclass(frozen=True)
class Verdict:
    tier: str  # exact|tolerant|amount_mismatch|credit_note|no_bill|unknown_supplier
    recommendation: str  # accept|review
    note: str
    matched_bill_number: str | None


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _inr(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def classify(
    *,
    doc_type: str,
    doc_number: str,
    total_paise: int,
    tax_paise: int,
    supplier_name: str,
    bills: Sequence[BillLite],
    known_suppliers: frozenset[str],
) -> Verdict:
    """Deterministic recommendation for one IMS record.

    Never recommends outright rejection — a wrong reject punishes the
    supplier's filing; anything not provably matched goes to human review
    with the evidence spelled out. Pure function: unit-tested without a DB.
    """
    if doc_type == "credit_note":
        return Verdict(
            tier="credit_note",
            recommendation="review",
            note=(
                f"Credit note — accepting reduces your ITC by {_inr(tax_paise)}; "
                "verify the underlying adjustment before acting."
            ),
            matched_bill_number=None,
        )

    by_number = {_norm(b.number): b for b in bills}
    bill = by_number.get(_norm(doc_number))
    if bill is not None:
        delta = abs(total_paise - bill.amount_paise)
        tolerance = max(TOLERANCE_PAISE, bill.amount_paise * TOLERANCE_BPS // 10_000)
        settled = (
            " Bill already settled — the purchase is genuine; ITC still claimable."
            if bill.status == "paid"
            else ""
        )
        if delta == 0:
            return Verdict(
                tier="exact",
                recommendation="accept",
                note=(
                    f"3-way ready: supplier filing matches purchase bill "
                    f"{bill.number} exactly.{settled}"
                ),
                matched_bill_number=bill.number,
            )
        if delta <= tolerance:
            return Verdict(
                tier="tolerant",
                recommendation="accept",
                note=(
                    f"{_inr(delta)} delta vs bill {bill.number} — rounding-level "
                    f"(within max(₹100, 0.25%)).{settled}"
                ),
                matched_bill_number=bill.number,
            )
        return Verdict(
            tier="amount_mismatch",
            recommendation="review",
            note=(
                f"Supplier filed {_inr(total_paise)}; your bill {bill.number} says "
                f"{_inr(bill.amount_paise)} — {_inr(delta)} apart. Resolve before accepting."
            ),
            matched_bill_number=bill.number,
        )

    if _norm(supplier_name) in known_suppliers:
        return Verdict(
            tier="no_bill",
            recommendation="review",
            note=(
                f"Supplier filed {doc_number}; no matching purchase bill in your books — "
                "confirm goods/services were received before accepting."
            ),
            matched_bill_number=None,
        )
    return Verdict(
        tier="unknown_supplier",
        recommendation="review",
        note=(
            "No purchase record for this supplier at all — possible wrong-GSTIN "
            "filing or a fraudulent claim. Reject if unrecognized."
        ),
        matched_bill_number=None,
    )


def itc_clock_rollup(
    rows: Sequence[Any], *, frequency: str, now: datetime
) -> dict[str, Any]:
    """Deemed-acceptance rollup across pending records. Pure.

    Answers the only question that matters once GSTR-3B Table 4 is hard-locked:
    how much credit is about to be decided for this tenant by doing nothing, and
    when. ``urgency`` is the worst band present, because a queue is exactly as
    urgent as its most urgent row.
    """
    pending = [r for r in rows if r.state == "pending"]
    empty = {
        "filing_frequency": frequency,
        "next_deadline": None,
        "days_remaining": None,
        "urgency": "safe",
        "itc_at_risk_paise": 0,
        "itc_lapsed_paise": 0,
        "lapsing_soon_paise": 0,
        "lapsed_count": 0,
    }
    if not pending:
        return empty

    snaps = [
        statutory.ims_clock_snapshot(
            period=r.period, now=now, frequency=frequency, tax_paise=r.tax_paise
        )
        for r in pending
    ]
    soonest = min(snaps, key=lambda s: s["days_remaining"])
    lapsed = [s for s in snaps if s["urgency"] == "lapsed"]
    return {
        "filing_frequency": frequency,
        "next_deadline": soonest["deemed_accept_at"],
        "days_remaining": soonest["days_remaining"],
        "urgency": soonest["urgency"],
        "itc_at_risk_paise": sum(s["itc_at_risk_paise"] for s in snaps),
        "itc_lapsed_paise": sum(s["itc_deemed_paise"] for s in snaps),
        "lapsing_soon_paise": sum(
            s["itc_at_risk_paise"] for s in snaps if s["urgency"] == "urgent"
        ),
        "lapsed_count": len(lapsed),
    }


def queue_totals(rows: Sequence[Any]) -> dict[str, int]:
    """Pure rollup used by the queue endpoint and tests."""
    pending = [r for r in rows if r.state == "pending"]
    return {
        "pending_count": len(pending),
        "itc_at_stake_paise": sum(r.tax_paise for r in pending),
        "review_count": sum(1 for r in pending if r.recommendation == "review"),
        "accept_ready_paise": sum(
            r.tax_paise for r in pending if r.recommendation == "accept"
        ),
        "accepted_tax_paise": sum(r.tax_paise for r in rows if r.state == "accepted"),
        "rejected_tax_paise": sum(r.tax_paise for r in rows if r.state == "rejected"),
    }


# ----------------------------------------------------------- DB operations


async def sync_and_match(
    session: AsyncSession,
    *,
    tenant_id: str,
    period: str,
    provider: Any,
    actor: dict[str, Any],
) -> dict[str, Any]:
    pulled = provider.pull_records(period=period)

    existing = {
        r.record_key: r
        for r in await session.scalars(
            select(ImsRecord).where(ImsRecord.tenant_id == tenant_id)
        )
    }
    created = refreshed = skipped_decided = 0
    for rec in pulled:
        row = existing.get(rec.key)
        if row is None:
            from findesk_shared import uuid7

            session.add(
                ImsRecord(
                    id=uuid7(),
                    tenant_id=tenant_id,
                    record_key=rec.key,
                    supplier_gstin=rec.supplier_gstin,
                    supplier_name=rec.supplier_name,
                    doc_type=rec.doc_type,
                    doc_number=rec.doc_number,
                    doc_date=datetime.fromisoformat(rec.doc_date).replace(tzinfo=UTC),
                    period=rec.period,
                    taxable_value_paise=rec.taxable_value_paise,
                    tax_paise=rec.tax_paise,
                    total_paise=rec.total_paise,
                    state="pending",
                )
            )
            created += 1
        elif row.state == "pending":
            row.taxable_value_paise = rec.taxable_value_paise
            row.tax_paise = rec.tax_paise
            row.total_paise = rec.total_paise
            row.period = rec.period
            refreshed += 1
        else:
            skipped_decided += 1  # decided is terminal for sync
    await session.flush()

    counts = await match_pending(session, tenant_id=tenant_id)
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action="ims.synced",
        entity_ref=f"ims:{period}",
        payload={
            "pulled": len(pulled),
            "created": created,
            "refreshed": refreshed,
            "skipped_decided": skipped_decided,
            **counts,
        },
    )
    return {
        "pulled": len(pulled),
        "created": created,
        "refreshed": refreshed,
        "skipped_decided": skipped_decided,
        **counts,
    }


async def match_pending(session: AsyncSession, *, tenant_id: str) -> dict[str, int]:
    """(Re)classify every pending record against the purchase register."""
    bills_rows = (
        await session.execute(
            select(Bill, Counterparty.name, Counterparty.gstin)
            .join(Counterparty, Counterparty.id == Bill.counterparty_id)
            .where(Bill.tenant_id == tenant_id)
        )
    ).all()
    bills = [
        BillLite(
            number=b.number,
            amount_paise=b.amount_paise,
            outstanding_paise=b.outstanding_paise,
            status=b.status,
            vendor=name,
        )
        for b, name, _g in bills_rows
    ]
    known = frozenset(_norm(name) for _b, name, _g in bills_rows)

    # write-through enrichment: a name-matched vendor with no GSTIN on file
    # gains one from the supplier's filing (fill-only, never overwrite)
    gstin_by_name: dict[str, str] = {}

    pending = list(
        await session.scalars(
            select(ImsRecord).where(
                ImsRecord.tenant_id == tenant_id, ImsRecord.state == "pending"
            )
        )
    )
    accept = review = 0
    for row in pending:
        verdict = classify(
            doc_type=row.doc_type,
            doc_number=row.doc_number,
            total_paise=row.total_paise,
            tax_paise=row.tax_paise,
            supplier_name=row.supplier_name,
            bills=bills,
            known_suppliers=known,
        )
        row.match_tier = verdict.tier
        row.recommendation = verdict.recommendation
        row.note = verdict.note
        row.matched_bill_number = verdict.matched_bill_number
        if verdict.recommendation == "accept":
            accept += 1
        else:
            review += 1
        if _norm(row.supplier_name) in known:
            gstin_by_name.setdefault(_norm(row.supplier_name), row.supplier_gstin)

    if gstin_by_name:
        parties = await session.scalars(
            select(Counterparty).where(
                Counterparty.tenant_id == tenant_id, Counterparty.gstin.is_(None)
            )
        )
        for party in parties:
            filed = gstin_by_name.get(_norm(party.name))
            if filed:
                party.gstin = filed
    await session.flush()
    return {"recommended_accept": accept, "needs_review": review}


async def list_queue(session: AsyncSession, *, tenant_id: str) -> list[ImsRecord]:
    rows = list(
        await session.scalars(
            select(ImsRecord).where(ImsRecord.tenant_id == tenant_id)
        )
    )
    order = {"pending": 0, "rejected": 1, "accepted": 2}
    rec_order = {"review": 0, "accept": 1, None: 2}
    rows.sort(
        key=lambda r: (
            order.get(r.state, 3),
            rec_order.get(r.recommendation, 2),
            -r.tax_paise,
        )
    )
    return rows
