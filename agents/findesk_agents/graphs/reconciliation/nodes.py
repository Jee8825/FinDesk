"""Reconciliation nodes: fetch → parse → ingest → recall → match → critic →
commit → learn. Tool = bank_statements; app data via internal backend API;
beliefs via Recall (best-effort in Phase 1)."""

from __future__ import annotations

import json
from datetime import datetime

from findesk_shared import format_inr, uuid7
from findesk_tools.bank_statements import ToolError, parse_statement

from findesk_agents.graphs.reconciliation import categorization, matching
from findesk_agents.graphs.reconciliation.state import ReconState
from findesk_agents.llm import get_critic_llm, render_prompt


async def fetch_and_parse(state: ReconState) -> dict:
    if not state.document_id:  # sweep run: nothing to parse
        return {}
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
    if not state.parsed:
        return {}
    step_id = uuid7()
    await state.emitter.step("ingest_transactions", "started", step_id)
    outcome = await state.backend.ingest_transactions(state.tenant_id, state.parsed)
    await state.emitter.step("ingest_transactions", "finished", step_id, **outcome)
    return {"ingested": outcome}


async def match(state: ReconState) -> dict:
    step_id = uuid7()
    await state.emitter.step("match", "started", step_id)
    context = await state.backend.recon_context(state.tenant_id)

    # recall-before-reason: remembered deduction patterns drive TDS matching
    notes: list[str] = []
    remembered_rates: dict[str, list[int]] = {}
    open_party_ids = {inv["counterparty_id"] for inv in context["open_invoices"]}
    parties_by_id = {p["id"]: p for p in context["counterparties"]}
    for party_id in open_party_ids:
        party = parties_by_id.get(party_id)
        if party is None:
            continue
        memories = await state.memory.recall(
            tenant_id=state.tenant_id,
            scope_key=f"client:{party_id}",
            query=f"TDS deduction and payment behavior of {party['name']}",
            token_budget=400,
        )
        if memories:
            notes.append(f"{party['name']}: {len(memories)} memories")
            rates = matching.parse_deduction_rates([m.get("content", "") for m in memories])
            if rates:
                remembered_rates[party_id] = rates
                notes.append(f"{party['name']}: remembered TDS {rates} bps")

    exact = matching.propose_matches(
        context["unmatched"], context["open_invoices"], context["counterparties"]
    )
    matched_txns = {p["bank_transaction_id"] for p in exact}
    matched_invoices = {p["invoice_id"] for p in exact}
    residual_txns = [t for t in context["unmatched"] if t["id"] not in matched_txns]
    residual_invoices = [
        i for i in context["open_invoices"] if i["id"] not in matched_invoices
    ]
    tds = matching.propose_tds_matches(
        residual_txns, residual_invoices, context["counterparties"], remembered_rates
    )
    proposals = [*exact, *tds]
    await state.emitter.step(
        "match",
        "finished",
        step_id,
        candidates=len(context["unmatched"]),
        proposals=len(proposals),
        tds_proposals=len(tds),
        memory=notes or ["unavailable or empty (skipped)"],
    )
    return {"context": context, "proposals": proposals, "memory_notes": notes}


async def categorize(state: ReconState) -> dict:
    """A3: categorize uncategorized debits — memory first, rules second."""
    step_id = uuid7()
    await state.emitter.step("categorize", "started", step_id)
    debits = state.context.get("uncategorized_debits", [])
    valid_codes = set(state.context.get("valid_category_codes", []))

    memory_claims: dict[str, tuple[str, float]] = {}
    for txn in debits:
        slug = categorization.vendor_slug(txn)
        if slug in memory_claims:
            continue
        memories = await state.memory.recall(
            tenant_id=state.tenant_id,
            scope_key=f"vendor:{slug}",
            query="expense category of this vendor",
            token_budget=400,
        )
        claim = categorization.parse_category_claims(memories)
        if claim:
            memory_claims[slug] = claim

    items = categorization.categorize(debits, memory_claims, valid_codes)
    outcome = (
        await state.backend.categorize(state.tenant_id, state.run_id, items)
        if items
        else {"applied": 0, "skipped": 0}
    )
    await state.emitter.step(
        "categorize",
        "finished",
        step_id,
        debits=len(debits),
        assigned=outcome["applied"],
        from_memory=sum(1 for i in items if i["source"] == "memory"),
    )
    return {"categorized": items, "vendor_claims_known": list(memory_claims)}


async def critic(state: ReconState) -> dict:
    step_id = uuid7()
    await state.emitter.step("critic", "started", step_id)
    reviewed = matching.critic_review(state.proposals, state.context["open_invoices"])

    # LLM second pass (Groq-gated): may veto a deterministic pass with a
    # reason, never revive a deterministic fail. Absent/failed LLM = no-op.
    checker = "deterministic-v0"
    llm = get_critic_llm()
    if llm is not None and any(p["critic_verdict"]["verdict"] == "pass" for p in reviewed):
        passes = [
            (i, p) for i, p in enumerate(reviewed) if p["critic_verdict"]["verdict"] == "pass"
        ]
        prompt = render_prompt(
            "agents/critic@v1",
            proposals=json.dumps([p for _, p in passes], default=str),
            counterparties=json.dumps(state.context.get("counterparties", [])),
        )
        result = await llm.complete_json(prompt)
        if result is not None:
            checker = f"deterministic-v0+llm:{llm.model}"
            for review in result.get("reviews", []):
                try:
                    idx = passes[int(review["index"])][0]
                except (KeyError, ValueError, IndexError):
                    continue
                if review.get("verdict") == "fail":
                    reviewed[idx]["critic_verdict"] = {
                        "verdict": "fail",
                        "problems": [f"llm: {review.get('reason', 'vetoed')}"],
                        "checker": checker,
                    }
            for p in reviewed:
                p["critic_verdict"].setdefault("checker", checker)
                p["critic_verdict"]["checker"] = checker

    passed = sum(1 for p in reviewed if p["critic_verdict"]["verdict"] == "pass")
    await state.emitter.step(
        "critic", "finished", step_id, reviewed=len(reviewed), passed=passed, checker=checker
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
    queued = result.get("queued", 0)
    unmatched = len(state.context.get("unmatched", [])) - committed - queued
    summary = (
        f"{inserted} new transactions; {committed} matched & posted; "
        f"{queued} awaiting approval; {max(unmatched, 0)} left for review"
    )
    return {"commit_result": result, "summary": summary}


async def learn(state: ReconState) -> dict:
    """Write observations back to memory (B1/A2 feedstock). Best-effort.

    Only *committed* outcomes become memories — queued proposals learn on
    approval (a later slice wires the approval decision back to memory).
    """
    step_id = uuid7()
    await state.emitter.step("learn", "started", step_id)
    stored = 0
    results = state.commit_result.get("results", [])
    for p, outcome in zip(state.proposals, results, strict=False):
        if not outcome.get("committed"):
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
        if p.get("kind") == "tds_adjusted":
            rate_pct = p["tds_bps"] / 100
            ok2 = await state.memory.remember(
                tenant_id=state.tenant_id,
                scope_key=f"client:{p['counterparty_id']}",
                run_id=state.run_id,
                content=(
                    f"This client deducts {rate_pct:g}% TDS on payments "
                    f"(seen on invoice {p['invoice_number']})."
                ),
            )
            stored += 1 if ok2 else 0

    # vendor_category claims for rule-assigned debits — only when no claim
    # exists yet for that vendor (the engine treats near-duplicate ingests as
    # conflicts, so repeated identical claims would spam the conflict queue)
    known = set(state.vendor_claims_known)
    claimed: set[str] = set()
    for item in state.categorized:
        slug = item["vendor_slug"]
        if item["source"] != "rule" or slug in known or slug in claimed:
            continue
        ok3 = await state.memory.remember(
            tenant_id=state.tenant_id,
            scope_key=f"vendor:{slug}",
            run_id=state.run_id,
            content=(
                f"Vendor '{item['vendor_label']}' expenses are categorized as "
                f"{item['category_code']}."
            ),
        )
        stored += 1 if ok3 else 0
        claimed.add(slug)
    await state.emitter.step("learn", "finished", step_id, observations=stored)
    return {"memory_notes": [*state.memory_notes, f"stored {stored} observations"]}
