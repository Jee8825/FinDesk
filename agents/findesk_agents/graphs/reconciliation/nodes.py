"""Reconciliation nodes: fetch → parse → ingest → recall → match → critic →
commit → learn. Tool = bank_statements; app data via internal backend API;
beliefs via Recall (best-effort in Phase 1)."""

from __future__ import annotations

from datetime import datetime

from findesk_shared import format_inr, uuid7
from findesk_tools.bank_statements import ToolError, parse_statement

from findesk_agents.graphs.reconciliation import matching
from findesk_agents.graphs.reconciliation.state import ReconState


async def fetch_and_parse(state: ReconState) -> dict:
    step_id = uuid7()
    await state.emitter.step("fetch_statement", "started", step_id)
    doc = await state.backend.document(state.document_id, state.tenant_id)
    await state.emitter.step("fetch_statement", "finished", step_id, filename=doc["filename"])

    step_id = uuid7()
    await state.emitter.step("parse_statement", "started", step_id, tool="bank_statements@v1")
    try:
        result = parse_statement(doc["content"])
    except ToolError as exc:
        await state.emitter.step(
            "parse_statement", "failed", step_id, error=exc.code, reason=exc.reason
        )
        raise
    rows = [
        {**t.model_dump(mode="json"), "dedupe_hash": t.dedupe_hash(), "source": {
            "kind": "bank_statement", "external_id": state.document_id,
        }}
        for t in result.transactions
    ]
    await state.emitter.step(
        "parse_statement",
        "finished",
        step_id,
        transactions=len(rows),
        skipped=result.skipped_rows,
        period=result.period,
    )
    return {"parsed": rows, "parse_meta": {"period": result.period}}


async def ingest(state: ReconState) -> dict:
    step_id = uuid7()
    await state.emitter.step("ingest_transactions", "started", step_id)
    outcome = await state.backend.ingest_transactions(state.tenant_id, state.parsed)
    await state.emitter.step("ingest_transactions", "finished", step_id, **outcome)
    return {"ingested": outcome}


async def match(state: ReconState) -> dict:
    step_id = uuid7()
    await state.emitter.step("match", "started", step_id)
    context = await state.backend.recon_context(state.tenant_id)

    # recall-before-reason: counterparty payment patterns inform future
    # matchers; v0 only proves the wiring and records what came back
    notes = []
    for party in context["counterparties"][:5]:
        memories = await state.memory.recall(
            tenant_id=state.tenant_id,
            scope_key=f"client:{party['id']}",
            query=f"payment behavior of {party['name']}",
            token_budget=400,
        )
        if memories:
            notes.append(f"{party['name']}: {len(memories)} memories")
    proposals = matching.propose_matches(
        context["unmatched"], context["open_invoices"], context["counterparties"]
    )
    await state.emitter.step(
        "match",
        "finished",
        step_id,
        candidates=len(context["unmatched"]),
        proposals=len(proposals),
        memory=notes or ["unavailable or empty (skipped)"],
    )
    return {"context": context, "proposals": proposals, "memory_notes": notes}


async def critic(state: ReconState) -> dict:
    step_id = uuid7()
    await state.emitter.step("critic", "started", step_id)
    reviewed = matching.critic_review(state.proposals, state.context["open_invoices"])
    passed = sum(1 for p in reviewed if p["critic_verdict"]["verdict"] == "pass")
    await state.emitter.step(
        "critic", "finished", step_id, reviewed=len(reviewed), passed=passed
    )
    return {"proposals": reviewed}


async def commit(state: ReconState) -> dict:
    step_id = uuid7()
    await state.emitter.step("commit", "started", step_id)
    result = (
        await state.backend.commit(state.tenant_id, state.run_id, state.proposals)
        if state.proposals
        else {"results": [], "committed": 0}
    )
    await state.emitter.step("commit", "finished", step_id, committed=result["committed"])

    inserted = state.ingested.get("inserted", 0)
    committed = result["committed"]
    unmatched = len(state.context.get("unmatched", [])) - committed
    summary = (
        f"{inserted} new transactions; {committed} matched & posted; "
        f"{max(unmatched, 0)} left for review"
    )
    return {"commit_result": result, "summary": summary}


async def learn(state: ReconState) -> dict:
    """Write payment observations back to memory (B1 feedstock). Best-effort."""
    step_id = uuid7()
    await state.emitter.step("learn", "started", step_id)
    stored = 0
    for p in state.proposals:
        if p.get("critic_verdict", {}).get("verdict") != "pass":
            continue
        paid = datetime.fromisoformat(p["txn_date"]).date()
        due = datetime.fromisoformat(p["due_date"]).date()
        delta = (paid - due).days
        timing = f"{delta} days late" if delta > 0 else f"{-delta} days early"
        ok = await state.memory.remember(
            tenant_id=state.tenant_id,
            scope_key=f"client:{p['counterparty_id']}",
            run_id=state.run_id,
            content=(
                f"Invoice {p['invoice_number']} ({format_inr(p['amount_paise'])}) was paid "
                f"{timing} relative to its due date {due.isoformat()}."
            ),
        )
        stored += 1 if ok else 0
    await state.emitter.step("learn", "finished", step_id, observations=stored)
    return {"memory_notes": [*state.memory_notes, f"stored {stored} observations"]}
