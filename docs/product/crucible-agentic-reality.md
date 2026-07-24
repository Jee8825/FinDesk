# FinDesk — Agentic Reality Check + Next-Round Feature Analysis

**Date:** 2026-07-24 · **Branch:** `feat/crucible-hardening` @ `62e4c91`
**Two questions:** (1) is the multi-agent AI real and working? (2) what should be
built next, given the shape the repo is actually in today?

Everything below is `[V]` verified against code at HEAD or a live probe run this
session, or `[I]` inferred from convergent external sources (cited).

> **Update — same session, after this audit.** Findings 1 and 9 are now partly
> addressed and one new defect was found *by turning the LLM on*:
>
> - **LLM providers are live.** Groq (primary) + OpenRouter (fallback) keys
>   configured; `llm.py` rewritten as an ordered candidate chain with heavy/light
>   roles and `provider:model` provenance recorded into the proposal's `checker`
>   field. Verified live: primary answers, forced-failover reaches OpenRouter,
>   all-fail still returns `None` (deterministic contract intact). 9 new tests.
> - **New defect, now fixed — the critic was judging blind.** Two of the critic
>   prompt's four veto criteria reason about the bank narration, but
>   `propose_matches` never puts `narration` in the proposal dict, so the LLM was
>   asked to detect counterparty mismatches from data that did not contain them.
>   Added `matching.evidence_for_review()` (narration join + explicit index).
>   Before: LLM passed a payment whose narration named a different company.
>   After: vetoed, `committed: 0`. **This defect was invisible while the LLM was
>   switched off** — a standing argument for keeping it on in CI.
> - **Light model is not fit for the critic seat** `[V]` — on the identical
>   proposal, `llama-3.1-8b-instant` returned `pass` where
>   `llama-3.3-70b-versatile` correctly returned `fail`. Keep the critic on heavy.
>
> Findings 2–8 (no conditional edges, hardcoded planner, no checkpointer, the
> `decide_approval` if-ladder, graph test coverage, observability) are unchanged
> and remain the substance of N4/N5.

---

## Part 1 — Is the multi-agent AI real?

**Verdict: the orchestration is real and production-shaped. The agency is not.
Right now the system makes zero LLM calls and every graph is a straight line.**

That is not the same as "it's fake." It is a genuinely good deterministic finance
engine wearing an agentic-AI label it has not yet earned. Both halves of that
sentence matter.

### Live probe (run this session, `scratchpad/agentic_probe.py`)

```
PROBE 1 — is an LLM reachable from the agents layer right now?
  get_critic_llm() -> None
  VERDICT: NO LLM — every graph runs 100% deterministic

PROBE 2 — does the LangGraph runtime actually execute? (recon graph)
  started/finished  match · categorize · critic · commit · learn
  critic  {'passed': 0, 'checker': 'deterministic-v0'}

PROBE 3 — graph topology: any branching / cycles / planner?
  nodes: 9  edges: 8   conditional edges: 0
  path: fetch_and_parse -> ingest -> match -> categorize -> critic -> commit -> learn
  VERDICT: STRAIGHT LINE — no decisions, no loops, no re-planning
```

### What is genuinely real `[V]`

| Claim | Reality |
|---|---|
| LangGraph state machines | **Real.** Compiled `StateGraph`s, typed Pydantic state, executed node-by-node (probe 2). |
| Redis Streams job bus | **Real and good.** Consumer groups, stable consumer name, PEL reclaim, dead-letter after max deliveries — `worker.py:111-164`. This is production-grade at-least-once. |
| SSE run streaming | **Real.** `routes_agent.py:149` — ordered relay, tenancy-checked before a byte streams. |
| Recall memory | **Real retrieval.** model2vec `potion-base-8M` 256-dim embeddings, live on `:8090`. Recall-before-reason genuinely runs in `match`/`categorize`/forecast, and `learn` writes observations back (`reconciliation/nodes.py:220`). |
| Deterministic guardrails | **Real and the best part of the repo.** Tool-layer `approval_token` refusals, hash-pinned action payloads, append-only audit chain. |
| Statutory engines | **Real.** Pure, test-vectored 45-day clock (`statutory.py`), forecast critic with pure invariants (`cash_forecast/critic.py`). |

### What is not real `[V]`

1. **Zero LLM calls happen at runtime.** `.env` contains exactly four keys —
   `APP_DATABASE_URL`, `APP_REDIS_URL`, `JWT_SECRET`, `RECALL_BASE_URL`. No LLM key.
   `get_critic_llm()` returns `None`, always. The single call site
   (`reconciliation/nodes.py:164`) never fires.
2. **Zero conditional edges in all 8 graphs.** `grep add_conditional_edges` → nothing.
   No branching, no cycles, no re-planning, no dynamic tool selection. Every graph is
   a fixed DAG. An "agent" that cannot choose is a pipeline.
3. **The Planner is a hardcoded list.** `ping/nodes.py:18` —
   `plan = ["check_pulse", "report"]` after `asyncio.sleep(0.2)  # simulated thinking`.
   This is the node the architecture docs cite as "Planner → Executor → Critic".
   It is honestly labelled Phase 0 in its own docstring; the README is less careful.
4. **Recall's LLM is a dev-echo shim.** `memory/infra/dev/embedding_shim.py` serves
   `/v1/chat/completions` with deterministic prompt-aware replies. Memory *extraction*
   is not LLM-driven in this environment either. Embeddings are real; the language
   model is a stub.
5. **"Multi-agent" is 8 single-agent pipelines.** No graph invokes another. No shared
   blackboard, no handoff, no negotiation. `worker.py:45` maps one job kind → one graph
   and that is the whole topology.
6. **No checkpointer, no `interrupt()`.** The approval gate does not suspend a graph.
   `decide_approval` (`approvals.py:80`) executes the consequential action *itself*, via
   a hardcoded ladder — `if action_kind == "ims_set_state"` … `"treds_listing"` …
   `"send_email"` — each with inline `from findesk_tools.X import` mid-function. The
   proposing run is long dead by then. Consequences: no durable resume (a worker crash
   mid-run replays from START), a 332-line service that grows an `if` branch per new
   action, and the backend acting as a tool caller in violation of its own layering.
7. **Graph-level test coverage is one graph.** Only `test_ping_graph.py` executes a
   compiled graph. The other 12 agent tests cover pure helpers (`matching`,
   `categorization`, `detection`, `engine`, critics, `letters`, `drafting`, `options`).
   No node function of recon / forecast / collections / anomaly / enforcer / wc / close
   is exercised. Root cause is mechanical: `ReconState` types `backend: BackendClient`
   and `memory: MemoryClient` **concretely**, so fakes fail Pydantic validation —
   the probe had to subclass to get in. Protocols here would make node tests trivial.
8. **Observability claim is still false.** Root `CLAUDE.md` and README claim
   "Langfuse + OpenTelemetry GenAI conventions; everything traced." `grep -rn
   "langfuse\|opentelemetry"` across `backend/ agents/ tools/ frontend/` returns two
   hits, both the string `otel_service_name` in a config default. Flagged in the last
   crucible round; unfixed.
9. **`prompts/` holds one prompt** against a hard rule titled "All prompts in `prompts/`".

### How to read this

For a product that moves money, deterministic-by-default is a **feature**, and
`agents/CLAUDE.md` is honest that every caller must degrade without an LLM. The
problem is not the architecture — it is that the claim layer says "multi-agentic AI"
and the code says "excellent deterministic finance engine with an optional LLM veto
that is switched off." An informed judge or a technical buyer resolves that gap in
about ten seconds, and the resolution is expensive because everything *else* in the
repo is unusually honest.

Two legitimate exits. Recommended: **N4 + N5 + N6 below** — make the agency real in
the three places where judgment genuinely exists, and never in the money math.

---

## Part 2 — What the landscape says to build (verified 2026-07-24)

Two facts changed the value of what is already built:

**L1. GSTR-3B Table 4 (ITC) hard-locking is targeted for ~July 2026 — i.e. now.** `[I]`
ITC becomes auto-populated from GSTR-2B/IMS and manually uneditable; corrections route
only through GSTR-1/1A on the supplier side. (Taxscan, CAclubindia, casanchar,
Lexology — convergent.) The IMS Copilot shipped last session stops being a convenience
and becomes the reason to buy.

**L2. Section 43B(h) is renumbered to Section 37(2)(g) under the Income-tax Act 2025,
in force 1 April 2026.** `[I]` Verified against a CBDT-FAQ deep-dive: FY 2025-26 (ended
31 Mar 2026) stays under the 1961 Act's §43B(h) via the §536 saving clause; Tax Year
2026-27 onward — *today* — is §37(2)(g). The **30 September 2026 tax-audit deadline**
(~9 weeks out) is the moment CAs work the FY 2025-26 MSME disallowance line.

**L3. IMS gained hard deadlines in the Oct-2025 tax period.** `[I]` Records may be kept
pending for **one tax period** (one month for monthly filers, one quarter for QRMP);
if no action is taken by the deadline, the system marks them **deemed accepted**.
Also added: partial ITC-reversal declaration, remarks on reject/pending, and an
**Import of Goods / Bill of Entry** section. (GSTN FAQ, Centax, gstsafar, Cashflo.)

---

## Recommendations, ranked by (impact ÷ effort)

### Tier 0 — credibility fixes, ~1–2 days total

**N1 · Tax-year-aware statute citation — 43B(h) *and* §37(2)(g).** ~1 day
`grep -c "43B"` across backend/frontend/agents/contracts = **36 citations, zero
tax-year awareness.** `payables.py` has an `fy_end()` helper but it is used for "pay
before FY-end to keep the deduction", never to select which statute governs. Today the
Payables Shield labels a Tax-Year-2026-27 bill under a section number from a repealed
Act. Fix: a `statute_citation(as_of) -> str` in `statutory.py`, threaded through
`payables.py`, `close.py:90`, and the UI. **This is a feature, not just a fix** —
"FinDesk cites the right statute for the year you are closing, and knows the transition"
is precisely the CA-trust story, and it lands nine weeks before the audit deadline that
makes CAs care.

**N2 · Close the observability gap.** ~0.5 day
Either wire it or drop the claim; recommend wiring. The emitter already emits
`step started/finished` with `step_id` — those *are* your span boundaries. OTel spans
around graph nodes + tool calls is a mechanical change, it makes the "glass box" pitch
literally true, and it gives the shipped Run Viewer a real backing store instead of
re-derived durations.

### Tier 1 — the flagship feature, 1–2 weeks

**N3 · The IMS Deemed-Accept Clock — FinDesk's second statutory clock.**
This is the highest-value thing available and it is timed to *this month*.

The gap, precisely: `ImsRecord` (`models.py:203`) has `state`, `period`, `tax_paise`,
`match_tier` — and **no deadline concept at all**. `grep -i "deemed\|pending_until\|
lapse"` across `services/ims.py` and `tools/findesk_tools/ims/` → nothing. So today
FinDesk shows an SME a queue of pending IMS records with no indication that ignoring
them silently *accepts* them, and — post-L1 — permanently fixes their ITC for the period.

Build:
- `pending_until` + `deemed_accept_at` on `ImsRecord`, derived from `period` + the
  tenant's filing frequency (monthly vs QRMP — a new Settings field).
- Extend `statutory.py` with an IMS clock alongside the §15 clock. Same shape: pure,
  deterministic, test-vectored. The engine already exists; this is a second instance
  of a proven pattern, not new machinery.
- Surface "**₹X of ITC will be deemed-accepted in N days**" on `/ims` and the dashboard.
- Make it a **blocking** close-checklist item — `close.py:119` already has
  "IMS queue actioned (ITC decided)" as a check; give it teeth and a countdown.
- Feed at-risk ITC into the forecast as a tagged driver. The pattern is already built
  (dated payables → firm outflows in their due weeks, commit `3a3b98a`).
- Close the three Oct-2025 IMS features the shipped copilot does not model: **partial
  ITC-reversal declaration**, **remarks on reject/pending** (a rejection without a
  reason is a supplier relationship you just damaged silently), and the **Import of
  Goods / Bill of Entry** section (any importing SME has ITC sitting there).

Why it is defensible: TallyPrime 7.x *surfaces* IMS discrepancies. Nobody is running a
**countdown with cash consequences** that **blocks your month-end close**. That is the
gap-widening move — up-stack from data entry, into statutory consequence, which is the
lane the last crucible round correctly identified as the only defensible one.

### Tier 2 — make the agency real, 1–2 weeks

**N4 · Resumable, interruptible runs.** *The single change that makes the architecture
diagram true.*
- Replace the `decide_approval` `if`-ladder with an **action executor registry**
  (`ACTION_EXECUTORS: dict[action_kind, Executor]`), so a new consequential action is a
  registration, not another `if` branch plus inline imports in a 332-line service.
- Add a LangGraph **Postgres checkpointer** + `interrupt()` at the approval gate. The
  graph *suspends*; approval *resumes* it. Today the graph dies and the backend does the
  work — which is why "human-in-the-loop agent" is currently a diagram, not a behaviour.
- Free win: durable resume means a worker crash mid-run stops replaying from START.

**N5 · Conditional edges in the three places judgment actually exists.** Not a sprinkle:
- **recon** `critic → {commit | escalate_for_review | rematch_with_tolerance}`. Today
  every proposal flows to `commit` and `recon.py:49` filters on verdict server-side —
  correct outcome, but the *agent* cannot choose a different action, only emit and hope.
- **collections**: route the ladder rung by memory-derived behaviour. A chronic-late
  payer and a first-miss should not get the same draft. The behaviour data is already
  in Recall and already recalled — it just cannot change the path.
- **close**: `blockers → remediation subgraph` instead of reporting "blocked on 19
  unmatched" and stopping.

**N6 · One genuinely LLM-powered surface, over a deterministic core.** ~3 days
The right one is the **month-end close narrative**: the deterministic engine produces
every number and every checklist verdict; the LLM writes the CFO-voice explanation of
numbers **it cannot change**, with values injected and a post-check asserting every ₹
figure in the output appears in the input. That is an LLM moment that survives an audit.
Second candidate: IMS reject-reason drafting (human-approved, never sent unreviewed).
Prerequisites: put a real key in `.env` (Groq is already wired end-to-end), and write
the prompts — `prompts/` currently holds one file against a hard rule demanding all of
them live there.

### Tier 3 — carried forward, needs a human decision

- **F6 CA multi-tenant rollup** — still blocked on hard rule 6 (no cross-tenant reads).
  Needs a decision on membership-scoped aggregation. Note the timing: the 30 Sep tax-audit
  deadline gives a CA-facing rollup real pull *right now*.
- **FE4 cookie migration** — documented pre-pilot gate, still open.
- **W1 live-Tally banked proof** — the README sentence "point it at a running TallyPrime
  to go live" has still never been demonstrated.
- **Graph node test coverage** — switch `BackendClient`/`MemoryClient` to Protocols in
  the state models and node tests become trivial to write. Currently blocked by concrete
  typing, which is why 7 of 8 graphs have no executed-node coverage.

---

## The one-line summary

The deterministic finance engine is real, well-tested, and genuinely differentiated.
The agentic AI layer is scaffolding with the lights off. **N1 + N3** buy the most
credibility per day (statute correctness + the ITC clock, both timed to July–September
2026 statutory events); **N4 + N5 + N6** are what it takes to make "multi-agentic"
a true statement rather than a label.

### Sources

- [Big GST Change from July 2026: GSTR-3B ITC Locking Explained — Taxscan](https://www.taxscan.in/top-stories/big-gst-change-from-july-2026-gstr-3b-itc-locking-explained-1448389)
- [Manual ITC Editing in GSTR-3B Discontinued from July 2026 — Pooja Jagdish & Associates](https://www.casanchar.com/blog/major-gst-update-manual-itc-editing-in-gstr-3b-discontinued-from-july-2026/)
- [Hard-locking GSTR-3B: A new compliance milestone and its pitfalls — Lexology](https://www.lexology.com/library/detail.aspx?g=1ef254e9-3fdc-417f-9177-55ee8ee88d24)
- [CBDT FAQ Deep-Dive #7: §43B(h) → §37(2)(g) under the Income-tax Act 2025 — Tax Update India](https://taxupdate.in/income-tax/771/cbdt-faq-deep-dive-7-section-43b-43bh-msme-section-37-income-tax-act-2025-actual-payment-tax-audit/)
- [GSTN Updates IMS to Allow Pending Records for One Tax Period — Centax](https://www.centaxonline.com/blog/gstn-updates-ims-to-allow-pending-records-for-one-tax-period)
- [Simplified IMS Process: Pending Records, ITC Declaration and Remark Facility — GST Safar](https://gstsafar.com/simplified-ims-process/)
- [Pending Option & ITC Reversal Feature Added in GST IMS — Cashflo](https://www.cashflo.io/magazine/pending-option-itc-reversal-feature-added-in-gst-ims)
- [GST IMS for MSMEs: Invoice Management System Guide — GimBooks](https://www.gimbooks.com/blog/gst-invoice-management-system-ims-guide-for-msmes/)
