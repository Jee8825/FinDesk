"""Collections nodes: fetch overdue → recall behavior → draft → queue.

The graph NEVER sends. Every draft becomes a ``send_email`` approval; the
backend executes approved sends through the email tool with a single-use
token (guardrail P2).
"""

from __future__ import annotations

from datetime import UTC, datetime

from findesk_shared import uuid7

from findesk_agents.graphs.collections import drafting
from findesk_agents.graphs.collections.state import CollectionsState


async def fetch_overdue(state: CollectionsState) -> dict:
    step_id = uuid7()
    await state.emitter.step("fetch_overdue", "started", step_id)
    context = await state.backend.collections_context(state.tenant_id)
    await state.emitter.step(
        "fetch_overdue", "finished", step_id, overdue=len(context["overdue"])
    )
    return {"overdue": context["overdue"], "sender_name": context["sender_name"]}


def route_after_fetch(state: CollectionsState) -> str:
    """Nothing overdue is a real outcome, not a zero-row pass through the mill."""
    return "draft" if state.overdue else "nothing_due"


async def nothing_due(state: CollectionsState) -> dict:
    """Clean ledger: skip the recall fan-out and the queue call entirely.

    Not intelligence — a guard. Worth a branch anyway: the draft node issues one
    memory query per client before it discovers it has no clients, and the old
    summary ("0 overdue invoices; 0 chaser drafts awaiting approval") read like
    a degraded run rather than a clean one.
    """
    step_id = uuid7()
    await state.emitter.step("nothing_due", "started", step_id)
    await state.emitter.step("nothing_due", "finished", step_id, overdue=0)
    return {"queued": 0, "summary": "No overdue invoices — nothing to chase."}


async def draft(state: CollectionsState) -> dict:
    step_id = uuid7()
    await state.emitter.step("draft", "started", step_id)
    now = datetime.now(UTC)
    client_ids = sorted({item["client"]["id"] for item in state.overdue})
    recalled = await state.memory.recall_many(
        tenant_id=state.tenant_id,
        queries=[
            (f"client:{cid}", "payment behavior and reliability of this client")
            for cid in client_ids
        ],
    )
    drafts = []
    for item in state.overdue:
        invoice, client = item["invoice"], item["client"]
        profile = drafting.behavior_profile(recalled.get(f"client:{client['id']}", []))
        days_overdue = (now - datetime.fromisoformat(invoice["due_date"])).days
        composed = drafting.compose_draft(
            invoice, client, profile, days_overdue=days_overdue, sender_name=state.sender_name
        )
        drafts.append(
            {
                **composed,
                "to": client.get("emails") or [],
                "invoice_id": invoice["id"],
                "invoice_number": invoice["number"],
                "amount_paise": invoice["amount_paise"],
                "counterparty_id": client["id"],
                "counterparty_name": client["name"],
                "days_overdue": days_overdue,
                "behavior": profile,
            }
        )
    tones = sorted({d["tone"] for d in drafts})
    await state.emitter.step("draft", "finished", step_id, drafts=len(drafts), tones=tones)
    return {"drafts": drafts}


async def queue_for_approval(state: CollectionsState) -> dict:
    step_id = uuid7()
    await state.emitter.step("queue_approvals", "started", step_id)
    sendable = [d for d in state.drafts if d["to"]]
    skipped = len(state.drafts) - len(sendable)
    outcome = (
        await state.backend.queue_email_approvals(state.tenant_id, state.run_id, sendable)
        if sendable
        else {"queued": 0, "duplicates": 0}
    )
    await state.emitter.step(
        "queue_approvals",
        "finished",
        step_id,
        queued=outcome["queued"],
        already_pending=outcome["duplicates"],
        no_contact=skipped,
    )
    summary = (
        f"{len(state.overdue)} overdue invoices; {outcome['queued']} chaser drafts "
        f"awaiting approval"
        + (f"; {skipped} skipped (no contact email)" if skipped else "")
    )
    return {"queued": outcome["queued"], "summary": summary}
