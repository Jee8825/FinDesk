"""LeakRadar nodes: fetch → canonicalize → recurrence → {drift → score | none} → critic → persist.

Division of labour is deliberate. Every number is produced by the pure detectors
(`recurrence`, `drift`, `scoring`); the LLM only ever touches *language* — it
renames messy payees and writes explanations of figures it cannot alter. If it is
unavailable, the deterministic slug and the deterministic reason string carry the
whole feature.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from findesk_shared import format_inr, uuid7, vendor_slug

from findesk_agents.graphs.anomaly_scan.detection import detect_duplicates
from findesk_agents.graphs.subscription_scan import drift, recurrence, scoring
from findesk_agents.graphs.subscription_scan.state import SubscriptionState
from findesk_agents.llm import get_llm, render_prompt

# Cap what we send to the LLM: canonicalization is per-vendor, so a huge book
# would otherwise blow the context and the free-tier token budget in one call.
CANONICAL_BATCH = 40
NARRATIVE_BATCH = 15


async def fetch(state: SubscriptionState) -> dict:
    step_id = uuid7()
    await state.emitter.step("fetch", "started", step_id)
    ctx = await state.backend.leak_context(state.tenant_id)
    debits = ctx["debits"]
    for t in debits:
        t["vendor_slug"] = vendor_slug(t.get("counterparty_hint"), t.get("narration", ""))
    await state.emitter.step(
        "fetch", "finished", step_id, debits=len(debits), mode=ctx["mode"]
    )
    return {"debits": debits, "mode": ctx["mode"]}


async def canonicalize(state: SubscriptionState) -> dict:
    """Give each vendor group a human-readable name.

    The grouping itself stays deterministic — `vendor_slug` decides which charges
    belong together, and the LLM is not allowed to merge or split groups, because
    a wrong merge would silently corrupt every cadence and drift verdict
    downstream. It only supplies a better *label*.
    """
    step_id = uuid7()
    await state.emitter.step("canonicalize", "started", step_id)

    groups: dict[str, list[dict[str, Any]]] = {}
    for t in state.debits:
        groups.setdefault(t["vendor_slug"], []).append(t)
    # deterministic fallback label, used as-is when no LLM is configured
    labels = {
        slug: (txns[0].get("counterparty_hint") or txns[0].get("narration", "")[:40])
        for slug, txns in groups.items()
    }

    renamed = 0
    llm = get_llm("light")
    if llm is not None and groups:
        payload = [
            {"slug": slug, "narrations": [t["narration"] for t in txns[:2]]}
            for slug, txns in sorted(groups.items())[:CANONICAL_BATCH]
        ]
        result = await llm.complete_json(
            render_prompt("agents/vendor_canonical@v1", vendors=json.dumps(payload))
        )
        for entry in (result or {}).get("vendors", []):
            slug, name = entry.get("slug"), (entry.get("name") or "").strip()
            # only rename slugs we actually asked about — a hallucinated slug
            # must never introduce a vendor that has no transactions
            if slug in labels and 0 < len(name) <= 40:
                labels[slug] = name
                renamed += 1

    for t in state.debits:
        t["vendor_label"] = labels[t["vendor_slug"]]

    await state.emitter.step(
        "canonicalize",
        "finished",
        step_id,
        vendors=len(groups),
        renamed=renamed,
        by=llm.model if llm else "deterministic-slug",
    )
    return {
        "canonical_notes": [f"{len(groups)} vendors, {renamed} renamed by model"],
    }


async def detect_recurrence(state: SubscriptionState) -> dict:
    step_id = uuid7()
    await state.emitter.step("detect_recurrence", "started", step_id)
    now = datetime.now(UTC)
    cadences = recurrence.detect_all(state.debits, now=now)
    for slug, c in cadences.items():
        group = [t for t in state.debits if t["vendor_slug"] == slug]
        c["vendor_label"] = group[0].get("vendor_label") or c["vendor_label"]

    dups: dict[str, int] = {}
    for finding in detect_duplicates(state.debits):
        slug = vendor_slug(None, finding["vendor_label"])
        dups[slug] = dups.get(slug, 0) + (finding.get("recoverable_paise") or 0)

    cadence_mix: dict[str, int] = {}
    for c in cadences.values():
        cadence_mix[c["cadence"]] = cadence_mix.get(c["cadence"], 0) + 1

    await state.emitter.step(
        "detect_recurrence",
        "finished",
        step_id,
        series=len(cadences),
        duplicates=len(dups),
        cadences=cadence_mix,
    )
    return {"cadences": cadences, "duplicates": dups}


def route_after_recurrence(state: SubscriptionState) -> str:
    """No recurring vendor means no leak table — do not run drift and scoring
    over an empty set to produce an empty page."""
    return "score" if state.cadences else "nothing_recurring"


async def nothing_recurring(state: SubscriptionState) -> dict:
    step_id = uuid7()
    await state.emitter.step("nothing_recurring", "started", step_id)
    await state.emitter.step(
        "nothing_recurring", "finished", step_id, debits=len(state.debits)
    )
    return {
        "rows": [],
        "totals": scoring.portfolio_totals([]),
        "summary": (
            f"No recurring vendors found in {len(state.debits)} debits — "
            "at least three charges from one vendor are needed to call it a series."
        ),
    }


async def recall_usage(state: SubscriptionState) -> dict:
    """What the human has already told us about these vendors.

    The only leak signal bank data cannot produce. Stored in Recall so it decays:
    an answer from a year ago is worth re-asking, and this is the mechanism that
    makes "unused" an answer rather than a guess.
    """
    step_id = uuid7()
    await state.emitter.step("recall_usage", "started", step_id)
    slugs = sorted(state.cadences)
    recalled = await state.memory.recall_many(
        tenant_id=state.tenant_id,
        queries=[
            (f"vendor:{slug}", "does the user still use this subscription")
            for slug in slugs
        ],
    )
    usage: dict[str, str] = {}
    for slug in slugs:
        for m in recalled.get(f"vendor:{slug}", []):
            content = (m.get("content") or "").lower()
            if "no longer uses" in content or "confirmed unused" in content:
                usage[slug] = "unused"
                break
            if "still uses" in content or "confirmed in use" in content:
                usage[slug] = "in_use"
                break
    await state.emitter.step(
        "recall_usage", "finished", step_id, known=len(usage), asked_about=len(slugs)
    )
    return {"usage": usage}


async def score(state: SubscriptionState) -> dict:
    step_id = uuid7()
    await state.emitter.step("score", "started", step_id)
    peers = scoring.category_peer_counts(list(state.cadences.values()))
    rows = []
    for slug, cadence in state.cadences.items():
        verdict = drift.analyse(cadence)
        row = scoring.score_one(
            cadence,
            verdict,
            mode=state.mode,
            duplicate_paise=state.duplicates.get(slug, 0),
            category_peers=peers.get(cadence["category_code"], 1),
            usage=state.usage.get(slug),
        )
        row |= {
            "period_days": cadence["period_days"],
            "periods_per_year": cadence["periods_per_year"],
            "occurrences": cadence["occurrences"],
            "confidence": cadence["confidence"],
            "first_seen": cadence["first_seen"],
            "last_seen": cadence["last_seen"],
            "next_expected": cadence["next_expected"],
            "latest_amount_paise": cadence["latest_amount_paise"],
            "amount_paise": cadence["amount_paise"],
            "evidence": {
                "step_change": verdict.get("step_change"),
                "seat_creep": verdict.get("seat_creep"),
                "amounts": cadence["amounts"],
                "dates": cadence["dates"],
                "gap_dispersion": cadence["gap_dispersion"],
            },
        }
        rows.append(row)
    rows = scoring.rank(rows)
    totals = scoring.portfolio_totals(rows)
    await state.emitter.step(
        "score",
        "finished",
        step_id,
        rows=len(rows),
        leaking=totals["leaking_count"],
        recoverable=totals["recoverable_paise_per_year"],
    )
    return {"rows": rows, "totals": totals}


async def narrate(state: SubscriptionState) -> dict:
    """Plain-English explanation per row, over numbers the model cannot change.

    Post-checked: every rupee figure in the sentence must appear in what we sent.
    A narrative that invents a number is worse than no narrative, so a failing
    sentence is dropped rather than shown.
    """
    step_id = uuid7()
    await state.emitter.step("narrate", "started", step_id)
    llm = get_llm("light")
    rows = state.rows
    if llm is None or not rows:
        await state.emitter.step(
            "narrate", "finished", step_id, written=0, by="deterministic-reason"
        )
        return {}

    candidates = [r for r in rows if r["leak_score"] > 0][:NARRATIVE_BATCH]
    payload = [
        {
            "slug": r["vendor_slug"],
            "vendor": r["vendor_label"],
            "cadence": r["cadence"],
            "annual_cost": format_inr(r["run_rate_paise"]),
            "recoverable_per_year": format_inr(r["recoverable_paise_per_year"]),
            "finding": r["reason"],
        }
        for r in candidates
    ]
    written = rejected = 0
    if payload:
        result = await llm.complete_json(
            render_prompt("agents/leak_narrative@v1", rows=json.dumps(payload))
        )
        allowed = {p["slug"]: p for p in payload}
        by_slug = {r["vendor_slug"]: r for r in rows}
        for note in (result or {}).get("notes", []):
            slug, text = note.get("slug"), (note.get("text") or "").strip()
            if slug not in allowed or not text or len(text) > 200:
                continue
            if _invents_a_number(text, allowed[slug]):
                rejected += 1
                continue
            by_slug[slug]["narrative"] = text
            written += 1

    await state.emitter.step(
        "narrate",
        "finished",
        step_id,
        written=written,
        rejected=rejected,
        by=llm.model,
    )
    return {"rows": rows}


def _invents_a_number(text: str, source: dict[str, Any]) -> bool:
    """True if the sentence contains a rupee figure we did not supply."""
    import re

    supplied = " ".join(str(v) for v in source.values())
    for token in re.findall(r"₹[\d,]+(?:\.\d+)?", text):
        if token not in supplied:
            return True
    return False


async def critic_review(state: SubscriptionState) -> dict:
    """Critic seat: a table someone will cancel real services from must be
    internally consistent."""
    from findesk_agents.graphs.subscription_scan import critic

    step_id = uuid7()
    await state.emitter.step("critic", "started", step_id)
    problems = critic.review(state.rows, state.totals)
    await state.emitter.step("critic", "finished", step_id, violations=len(problems))
    if problems:
        raise RuntimeError(f"leak critic rejected scan: {'; '.join(problems[:3])}")
    return {}


async def persist(state: SubscriptionState) -> dict:
    step_id = uuid7()
    await state.emitter.step("persist", "started", step_id)
    outcome = await state.backend.persist_leaks(
        state.tenant_id, state.run_id, state.rows
    )
    await state.emitter.step("persist", "finished", step_id, **outcome)
    t = state.totals
    summary = (
        f"{t['subscriptions']} recurring vendors · "
        f"{format_inr(t['committed_paise_per_year'])}/yr committed · "
        f"{format_inr(t['recoverable_paise_per_year'])}/yr recoverable across "
        f"{t['leaking_count']} leak(s)"
    )
    if t["unreviewed_count"]:
        summary += f" · {t['unreviewed_count']} never reviewed"
    return {"summary": summary}
