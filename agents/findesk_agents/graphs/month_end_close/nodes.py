"""month_end_close nodes: fetch checklist → critic → persist evidence run.

The graph assembles and audits the close *evidence*; it never signs off —
sign-off stays a human maker-checker act on /reports (POST /close/signoff).
"""

from __future__ import annotations

from findesk_shared import uuid7

from findesk_agents.graphs.month_end_close.state import CloseState


async def fetch_checklist(state: CloseState) -> dict:
    step_id = uuid7()
    await state.emitter.step("fetch_checklist", "started", step_id)
    ctx = await state.backend.close_context(state.tenant_id)
    checklist = ctx["checklist"]
    await state.emitter.step(
        "fetch_checklist",
        "finished",
        step_id,
        checks=len(checklist.get("checks", [])),
        blockers=len(checklist.get("blockers", [])),
        warnings=len(checklist.get("warnings", [])),
    )
    return {"period": ctx["period"], "checklist": checklist}


async def critic_review(state: CloseState) -> dict:
    """Critic seat: the artifact a human signs must be self-consistent."""
    from findesk_agents.graphs.month_end_close import critic

    step_id = uuid7()
    await state.emitter.step("critic", "started", step_id)
    problems = critic.review(state.checklist)
    await state.emitter.step("critic", "finished", step_id, violations=len(problems))
    if problems:
        raise RuntimeError(f"close critic rejected checklist: {'; '.join(problems[:3])}")
    return {}


async def persist(state: CloseState) -> dict:
    step_id = uuid7()
    await state.emitter.step("persist", "started", step_id)
    result = await state.backend.persist_close_run(
        state.tenant_id, state.run_id, period=state.period, checklist=state.checklist
    )
    await state.emitter.step("persist", "finished", step_id, ready=result["ready"])
    status = (
        "ready to sign off"
        if result["ready"]
        else f"blocked: {', '.join(result['blockers'])}"
    )
    warn = f" · {len(result['warnings'])} warning(s)" if result["warnings"] else ""
    return {"summary": f"Close {state.period} — {status}{warn}."}
