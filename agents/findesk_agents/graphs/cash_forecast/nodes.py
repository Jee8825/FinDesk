"""Cash-forecast nodes: fetch → recall behavior → project → persist."""

from __future__ import annotations

from datetime import UTC, datetime

from findesk_shared import parse_late_days, uuid7

from findesk_agents.graphs.anomaly_scan import detection
from findesk_agents.graphs.cash_forecast import engine
from findesk_agents.graphs.cash_forecast.state import ForecastState


async def fetch(state: ForecastState) -> dict:
    step_id = uuid7()
    await state.emitter.step("fetch_context", "started", step_id)
    ctx = await state.backend.forecast_context(state.tenant_id)
    await state.emitter.step(
        "fetch_context",
        "finished",
        step_id,
        opening_balance=ctx["opening_balance_paise"],
        open_invoices=len(ctx["open_invoices"]),
    )
    return {
        "opening_balance_paise": ctx["opening_balance_paise"],
        "open_invoices": ctx["open_invoices"],
        "debits": ctx["debits"],
        "open_bills": ctx.get("open_bills", []),
    }


async def recall_behavior(state: ForecastState) -> dict:
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
    spread: dict[str, float] = {}
    for cid in client_ids:
        lates = parse_late_days(
            [m.get("content", "") for m in recalled.get(f"client:{cid}", [])]
        )
        if lates:
            stats = engine.behavior_stats(lates)
            avg_late[cid] = stats["median_late"]  # median: robust to one-offs
            spread[cid] = stats["spread_days"]
    await state.emitter.step(
        "recall_behavior", "finished", step_id, clients_with_history=len(avg_late)
    )
    return {"avg_late_by_client": avg_late, "spread_by_client": spread}


async def projector(state: ForecastState) -> dict:
    step_id = uuid7()
    await state.emitter.step("project", "started", step_id)
    monthly_outflows = detection.baseline_claims(state.debits)
    result = engine.project(
        start=datetime.now(UTC),
        opening_balance_paise=state.opening_balance_paise,
        open_invoices=state.open_invoices,
        avg_late_by_client=state.avg_late_by_client,
        monthly_outflows=monthly_outflows,
        spread_by_client=state.spread_by_client,
        open_bills=state.open_bills,
    )
    await state.emitter.step(
        "project",
        "finished",
        step_id,
        recurring_vendors=len(monthly_outflows),
        weekly_outflow=result["weekly_outflow_paise"],
        gap_week=(result["gap"] or {}).get("week"),
    )
    return {"result": result}


async def persist(state: ForecastState) -> dict:
    step_id = uuid7()
    await state.emitter.step("persist", "started", step_id)
    await state.backend.persist_forecast(state.tenant_id, state.run_id, state.result)
    await state.emitter.step("persist", "finished", step_id)
    return {"summary": " ".join(state.result["narrative"])}
