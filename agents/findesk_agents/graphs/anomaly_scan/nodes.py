"""Anomaly-scan nodes: fetch → recall baselines → detect → persist → learn."""

from __future__ import annotations

import re

from findesk_shared import format_inr, uuid7

from findesk_agents.graphs.anomaly_scan import detection
from findesk_agents.graphs.anomaly_scan.state import AnomalyState

_BASELINE_RE = re.compile(r"consistently around ₹([\d,]+)")


async def fetch(state: AnomalyState) -> dict:
    step_id = uuid7()
    await state.emitter.step("fetch_debits", "started", step_id)
    context = await state.backend.anomaly_context(state.tenant_id)
    await state.emitter.step("fetch_debits", "finished", step_id, debits=len(context["debits"]))
    return {"debits": context["debits"]}


async def recall_baselines(state: AnomalyState) -> dict:
    step_id = uuid7()
    await state.emitter.step("recall_baselines", "started", step_id)
    vendors = sorted({detection.slug(t) for t in state.debits})
    recalled = await state.memory.recall_many(
        tenant_id=state.tenant_id,
        queries=[(f"vendor:{v}", "usual monthly bill amount for this vendor") for v in vendors],
    )
    baselines: dict[str, list[int]] = {}
    for vendor in vendors:
        amounts = []
        for m in recalled.get(f"vendor:{vendor}", []):
            match = _BASELINE_RE.search(m.get("content", ""))
            if match:
                amounts.append(int(match.group(1).replace(",", "")) * 100)
        if amounts:
            baselines[vendor] = amounts
    await state.emitter.step(
        "recall_baselines", "finished", step_id, vendors_with_memory=len(baselines)
    )
    return {"memory_baselines": baselines}


async def detect(state: AnomalyState) -> dict:
    step_id = uuid7()
    await state.emitter.step("detect", "started", step_id)
    findings = [
        *detection.detect_duplicates(state.debits),
        *detection.detect_deviations(state.debits, state.memory_baselines),
    ]
    await state.emitter.step(
        "detect",
        "finished",
        step_id,
        findings=len(findings),
        kinds=sorted({f["kind"] for f in findings}),
    )
    return {"findings": findings}


async def persist(state: AnomalyState) -> dict:
    step_id = uuid7()
    await state.emitter.step("persist", "started", step_id)
    outcome = (
        await state.backend.persist_anomalies(state.tenant_id, state.run_id, state.findings)
        if state.findings
        else {"created": 0, "existing": 0}
    )
    recoverable = sum(f.get("recoverable_paise") or 0 for f in state.findings)
    summary = (
        f"{outcome['created']} new anomalies "
        f"({format_inr(recoverable)} potentially recoverable)"
        if outcome["created"]
        else "no new anomalies — books look clean"
    )
    await state.emitter.step("persist", "finished", step_id, **outcome)
    return {"persisted": outcome, "summary": summary}


async def learn(state: AnomalyState) -> dict:
    """Remember stable vendor baselines (anomaly_baseline claims), once each."""
    step_id = uuid7()
    await state.emitter.step("learn", "started", step_id)
    stored = 0
    claims = detection.baseline_claims(state.debits)
    for vendor, baseline in claims.items():
        if vendor in state.memory_baselines:
            continue  # already remembered — re-ingest would raise a false conflict
        ok = await state.memory.remember(
            tenant_id=state.tenant_id,
            scope_key=f"vendor:{vendor}",
            run_id=state.run_id,
            content=(
                f"This vendor bills consistently around "
                f"₹{baseline // 100:,} per cycle."
            ),
        )
        stored += 1 if ok else 0
    await state.emitter.step("learn", "finished", step_id, baselines_stored=stored)
    return {}
