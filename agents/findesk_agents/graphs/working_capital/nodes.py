"""Working-capital nodes: fetch → recall behavior → build options → persist.

The graph never lists anything on TReDS — options are persisted as
``proposed`` and the human requests/approves execution through the queue.
"""

from __future__ import annotations

from datetime import UTC, datetime

from findesk_shared import format_inr, parse_late_days, uuid7
from findesk_tools.treds import SandboxTredsProvider

from findesk_agents.graphs.working_capital import options as option_builder
from findesk_agents.graphs.working_capital.state import WorkingCapitalState

_provider = SandboxTredsProvider()


def _quote_fn(invoice_ref: str, amount_paise: int, tenor_days: int) -> dict:
    return _provider.quote(
        invoice_ref=invoice_ref, amount_paise=amount_paise, tenor_days=tenor_days
    ).model_dump()


async def fetch(state: WorkingCapitalState) -> dict:
    step_id = uuid7()
    await state.emitter.step("fetch_context", "started", step_id)
    ctx = await state.backend.forecast_context(state.tenant_id)
    gap = await state.backend.latest_gap(state.tenant_id)
    await state.emitter.step(
        "fetch_context",
        "finished",
        step_id,
        open_invoices=len(ctx["open_invoices"]),
        forecast_gap=(gap or {}).get("week"),
    )
    return {"open_invoices": ctx["open_invoices"], "gap": gap}


async def recall_behavior(state: WorkingCapitalState) -> dict:
    step_id = uuid7()
    await state.emitter.step("recall_behavior", "started", step_id)
    client_ids = sorted({inv["client_id"] for inv in state.open_invoices})
    recalled = await state.memory.recall_many(
        tenant_id=state.tenant_id,
        queries=[
            (f"client:{cid}", "payment behavior: how late does this client pay?")
            for cid in client_ids
        ],
    )
    avg_late: dict[str, float] = {}
    for cid in client_ids:
        lates = parse_late_days(
            [m.get("content", "") for m in recalled.get(f"client:{cid}", [])]
        )
        if lates:
            avg_late[cid] = round(sum(lates) / len(lates), 1)
    await state.emitter.step(
        "recall_behavior", "finished", step_id, clients_with_history=len(avg_late)
    )
    return {"avg_late_by_client": avg_late}


async def build(state: WorkingCapitalState) -> dict:
    step_id = uuid7()
    await state.emitter.step("build_options", "started", step_id)
    opts = option_builder.build_options(
        now=datetime.now(UTC),
        open_invoices=state.open_invoices,
        avg_late_by_client=state.avg_late_by_client,
        quote_fn=_quote_fn,
    )
    await state.emitter.step(
        "build_options",
        "finished",
        step_id,
        options=len(opts),
        kinds=sorted({o["kind"] for o in opts}),
    )
    return {"options": opts}


async def persist(state: WorkingCapitalState) -> dict:
    step_id = uuid7()
    await state.emitter.step("persist", "started", step_id)
    outcome = (
        await state.backend.persist_wc_actions(state.tenant_id, state.run_id, state.options)
        if state.options
        else {"created": 0, "existing": 0}
    )
    unlockable = sum(o["unlock_paise"] for o in state.options)
    summary = (
        f"{len(state.options)} working-capital options, "
        f"{format_inr(unlockable)} unlockable"
        + (
            f"; forecast gap in week {state.gap['week'] + 1} drives urgency"
            if state.gap
            else "; no forecast gap — options are opportunistic"
        )
    )
    await state.emitter.step("persist", "finished", step_id, **outcome)
    return {"summary": summary}
