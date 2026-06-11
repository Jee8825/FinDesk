"""Enforcer nodes: detect rung transitions → prepare artifacts → queue/persist.

The ladder states come from the statutory engine; this graph fires once per
rung crossing (the backend tracks last_enforced_level — no daily re-fires).
Act letters route through the send_email approval gate; Samadhaan documents
are persisted as preparations and never filed.
"""

from __future__ import annotations

from findesk_shared import uuid7

from findesk_agents.graphs.enforcer import letters
from findesk_agents.graphs.enforcer.state import EnforcerState


async def detect(state: EnforcerState) -> dict:
    step_id = uuid7()
    await state.emitter.step("detect_transitions", "started", step_id)
    ctx = await state.backend.enforcer_context(state.tenant_id)
    await state.emitter.step(
        "detect_transitions",
        "finished",
        step_id,
        transitions=len(ctx["transitions"]),
        levels=sorted({t["clock"]["escalation_level"] for t in ctx["transitions"]}),
    )
    return {
        "transitions": ctx["transitions"],
        "sender_name": ctx["sender_name"],
        "tenant_name": ctx["tenant_name"],
    }


async def prepare(state: EnforcerState) -> dict:
    step_id = uuid7()
    await state.emitter.step("prepare_artifacts", "started", step_id)
    letters_queued = 0
    samadhaan = 0
    for t in state.transitions:
        level = t["clock"]["escalation_level"]
        if level == "act_letter":
            draft = letters.act_letter(
                sender_name=state.sender_name,
                client_name=t["client"]["name"],
                invoice=t["invoice"],
                clock=t["clock"],
            )
            outcome = await state.backend.queue_act_letter(
                state.tenant_id,
                state.run_id,
                {
                    **draft,
                    "to": t["client"].get("emails") or [],
                    "invoice_id": t["invoice"]["id"],
                    "invoice_number": t["invoice"]["number"],
                    "amount_paise": t["invoice"]["amount_paise"],
                    "counterparty_id": t["client"]["id"],
                    "days_overdue": t["clock"]["overdue_days"],
                    "tone": "act_letter",
                    "thread_ref": f"invoice:{t['invoice']['id']}",
                    "level": level,
                },
            )
            letters_queued += 1 if outcome.get("queued") else 0
        elif level == "samadhaan_prep":
            doc = letters.samadhaan_prep(
                tenant_name=state.tenant_name,
                client_name=t["client"]["name"],
                invoice=t["invoice"],
                clock=t["clock"],
            )
            await state.backend.persist_samadhaan_prep(
                state.tenant_id,
                state.run_id,
                {
                    **doc,
                    "invoice_id": t["invoice"]["id"],
                    "invoice_number": t["invoice"]["number"],
                    "level": level,
                },
            )
            samadhaan += 1
    await state.emitter.step(
        "prepare_artifacts",
        "finished",
        step_id,
        act_letters_queued=letters_queued,
        samadhaan_prepared=samadhaan,
    )
    summary = (
        f"{letters_queued} Act letter(s) awaiting approval; "
        f"{samadhaan} Samadhaan preparation(s) drafted"
        if (letters_queued or samadhaan)
        else "no new escalation rungs crossed — nothing to enforce"
    )
    return {
        "letters_queued": letters_queued,
        "samadhaan_prepared": samadhaan,
        "summary": summary,
    }
