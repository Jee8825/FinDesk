"""Promise-to-pay + settlement write-back (F3: the outcome loop).

Before this, payment behavior entered memory exactly once — the onboarding
seed. Here every recon-committed settlement writes the observed lateness
(via the shared late_phrase twin, so the forecast's parser always reads it)
and classifies any open promise kept/broken. The forecast's recall path
consumes both without changing.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from findesk_shared import late_phrase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import memoryclient
from app.db.models import Counterparty, Invoice, PaymentPromise
from app.services.audit import write_audit


def settle_outcome(promised: date, paid: date) -> str:
    """Deterministic: paid on or before the promised date keeps the promise."""
    return "kept" if paid <= promised else "broken"


async def record_settlement(
    session: AsyncSession,
    *,
    tenant_id: str,
    invoice: Invoice,
    paid_on: date,
    actor: dict[str, Any],
) -> dict[str, Any]:
    """Write the lateness observation + settle open promises for one invoice.

    Memory writes degrade gracefully (memoryclient returns False when Recall
    is down) — settlement still audits and promise rows still settle.
    """
    delta = (paid_on - invoice.due_date.date()).days
    party = await session.get(Counterparty, invoice.counterparty_id)
    party_name = party.name if party else "client"

    claim = (
        f"Invoice {invoice.number} was paid {late_phrase(delta)} relative to its "
        f"due date {invoice.due_date.date().isoformat()}."
    )
    remembered = await memoryclient.remember(
        tenant_id=tenant_id,
        scope_key=f"client:{invoice.counterparty_id}",
        session_id=f"settle:{invoice.id}",
        content=claim,
    )

    promises = list(
        await session.scalars(
            select(PaymentPromise).where(
                PaymentPromise.tenant_id == tenant_id,
                PaymentPromise.invoice_id == invoice.id,
                PaymentPromise.status == "open",
            )
        )
    )
    outcomes: list[dict[str, Any]] = []
    for p in promises:
        p.status = settle_outcome(p.promised_date.date(), paid_on)
        outcomes.append(
            {"promise_id": p.id, "promised": p.promised_date.date().isoformat(), "status": p.status}
        )
        await memoryclient.remember(
            tenant_id=tenant_id,
            scope_key=f"client:{invoice.counterparty_id}",
            session_id=f"settle:{invoice.id}",
            content=(
                f"{party_name} {p.status} a promise-to-pay on invoice {invoice.number} "
                f"(promised {p.promised_date.date().isoformat()}, paid {paid_on.isoformat()})."
            ),
        )

    await write_audit(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action="receivable.settled",
        entity_ref=f"invoice:{invoice.id}",
        payload={
            "invoice_number": invoice.number,
            "late_days": delta,
            "behavior_remembered": remembered,
            "promises": outcomes,
        },
    )
    return {"late_days": delta, "promises_settled": len(outcomes), "remembered": remembered}
