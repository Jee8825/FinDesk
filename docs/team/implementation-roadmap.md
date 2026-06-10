# Implementation Roadmap — Phase by Phase

The build order exists to kill the two classic failure modes of an 8-person
agentic project: **integration rot** (layers built in isolation that don't
compose) and **trust debt** (impressive demos on top of wrong numbers). Hence
two rules that hold in every phase:

1. **Vertical slices, not horizontal layers.** A phase is done when a user
   can *do* something end-to-end on `dev` compose, not when a layer is "ready".
2. **Backend leads, frontend never waits.** Backend/data/agents carry the
   dependency chain (contracts → DB → API → graphs); frontend builds against
   the contract-generated client with mocked responses and swaps to real
   endpoints the day they exist. The contract is the synchronization point —
   not meetings.

Dependency chain that dictates the order:

```
contracts ──► app DB schema ──► backend services/API ──► agent graphs ──► frontend renders it
                  │                       │                  │
                  └── seed data           └── approval/SSE   └── memory + tools wiring
```

---

## Phase 0 — Make the skeleton run (everyone, ~first 2–3 days)

Goal: `make up` boots everything; CI hard-fails; one generated client.

| Workstream | Deliverable |
|---|---|
| Infra | compose services enabled (backend, worker, frontend) alongside memory stack; `make up` green on every laptop (override file for port collisions) |
| Contracts | `scripts/gen_contracts.py` real: api.yaml → `shared/py` models + `shared/ts` client; CI drift check switched to hard-fail |
| Backend | FastAPI app factory, healthz, settings, Alembic baseline (tenants/users/memberships), JWT login stub |
| Agents | worker process consuming `agents:interactive`, no-op `ping` graph writing `agent_runs`/`agent_steps`, Langfuse span wiring |
| Memory | Recall stack boots in-repo; smoke script: ingest + retrieve one `vendor_category` claim with FinDesk identity mapping |
| Frontend | Next.js scaffold, Tailwind/shadcn, auth shell, layout/nav for the page map, `useRunStream` hook against a mock SSE endpoint |
| All | `make seed` v0: one tenant, login works |

**Exit demo:** log in, click "run ping", watch live SSE steps render. It's
trivial — and it proves every layer talks to every layer. Most teams discover
their integration problems in week 5; we discover them here.

## Phase 1 — Walking skeleton of the product (Week 1)

Goal: the canonical data flow (00-overview §3) exists with the simplest
possible brains.

- **Ingestion (A1 minimal):** statement file upload → `bank_statements` tool
  parses CSV fixture → normalized `bank_transactions` rows, deduped.
- **Reconciliation v0 (A2 skeleton):** graph matches exact amount+date against
  seeded invoices — deterministic rules only, *no LLM yet*. Critic node exists
  but only checks sums. Commits via the real commit service.
- **Memory wired for real:** each match ingests a `payment_behavior`
  observation; the match node retrieves counterparty memory (even though v0
  barely uses it) — budgets, scoping, and run-id stamping proven now.
- **Frontend:** /books/transactions (real data), /books/reconciliation (live
  run), seed data expanded to a believable SME (6 months, ~40 counterparties).
- **Audit log + Why? v0:** every commit writes the chain; `/why` returns the
  raw trail (ugly is fine).

**Exit demo:** upload the fixture statement, watch the agent reconcile 70% of
it live, click a matched transaction → see why.

Why LLM-less first: it forces the *plumbing* (queues, checkpoints, commits,
SSE, tenancy) to be correct before model nondeterminism enters; every later
accuracy problem is then attributable to reasoning, not infrastructure.

## Phase 2 — Module A core: the trust machine (Weeks 2–3)

Goal: the four features that make FinDesk credible — matching intelligence,
consistency, conflicts, and the human loop. **This is the highest-risk phase;
nothing else starts until its slice demos.**

- **A2 full:** LLM matching for the residuals (partial payments, fees,
  **TDS-adjusted** — the ₹44,100/₹45,000 case), `deduction_pattern` claims
  learned and reused. Confidence floors from policy YAML enforced.
- **A3:** categorization with memory consistency + crystallization; chart-of-
  accounts UI view of crystallized mappings.
- **A5:** real Critic (independent re-derivation, logged verdicts).
- **A4:** write-time conflict detection → `conflicts` rows → **conflict card
  UI** with one-tap resolution → resolution posted back to memory+provenance.
- **Approval engine:** queue, single-use hash-bound tokens, run resume;
  /approvals UI. Guardrail engine v1 (P3 contested-commit veto live).
- **Eval harness v1:** golden reconciliation set; precision/recall + critic
  uplift measured in CI nightly. *Accuracy is a number from this phase on.*

**Exit demo:** messy fixture month → agent reconciles, raises 2 planted
conflicts, queue resolves them in one tap each, books update, eval report
prints accuracy.

## Phase 3 — Module A complete: the daily-use product (Weeks 4–5)

- **A1 full:** Tally/Zoho export import; AA consent flow behind a sandbox;
  onboarding flow with historical seeding into memory (12 months → semantic
  tier).
- **A6:** anomaly scan graph + `anomaly_baseline` memories + cards UI with
  recoverable-money flags (the "found money" conversion moment — make it the
  first-run experience).
- **A7:** collections graph, tone-calibrated drafts, **gated** email send
  (approval token → email tool), thread events feeding memory.
- **A8:** month-end close graph, report pack UI, polished Why? drawer.

**Exit demo:** fresh tenant onboards from a Tally export, first-run scan finds
planted duplicates/overcharges, month-end pack renders, one chaser email
approved and "sent" (sandbox).

## Phase 4 — Module B: cash command (Weeks 6–7)

Order inside the phase follows B's own dependency: B1 → (B2 ∥ B3) → B4 → B5.

- **B1:** payment observations → behavior distributions + drift detection
  (worsening-trend alerts).
- **B2:** statutory clock engine (pure, test-vectored, **built and reviewed
  before any UI**), radar UI, escalation ladder with prepared (never sent)
  artifacts, "review with your CA" framing.
- **B3:** scenario forecast engine consuming B1 distributions; bands+
  attribution UI; calibration eval added to the harness.
- **B4:** working-capital graph, TReDS quote tool (sandbox), P4 buyer-side
  45-day guardrail, ranked actions UI behind approvals.
- **B5:** data room export + FinDesk Score from provenance coverage.

**Exit demo:** the spec's hero story — week-7 gap predicted, attributed to one
client's worsening behavior, three costed actions offered, one approved.

## Phase 5 — Production hardening (Week 8+)

RLS enforced + cross-tenant tests; security pass on auth/approvals/webhooks;
PII-redaction verification on traces; integration suite green in CI; restore
drill; staging environment + demo tenant; CA multi-client console; calibration
results published in-product; load test on agent throughput.

---

## Who does what, when (ownership matrix × phases)

| Owner | P0 | P1 | P2 | P3 | P4 |
|---|---|---|---|---|---|
| Orchestration (1) | worker + ping graph | reconciliation v0 | LLM match + Critic | anomaly/collections/close graphs | B graphs |
| Tools (2) | MCP scaffold | bank_statements | — (support) | tally/zoho/email | treds/ims |
| Memory (3) | stack in-repo + smoke | identity wiring | claim kinds + conflict export | seeding + baselines | B1 distributions |
| DB (4) | baseline migration | books schema | conflicts/approvals/audit | documents/anomalies | cash schema |
| Backend (5–6) | auth + healthz | imports + SSE | approval engine + guardrails | reports + Why composition | clocks/forecast/actions |
| Frontend (7–8) | shell + mocks | transactions + run view | conflict cards + approvals | anomalies/collections/reports | radar/forecast/actions |
| Infra (rot.) | compose + CI hard-fail | seed v1 | eval harness | AA/email sandboxes | staging |

## Standing risk-reduction rules

- The **weekly smoke test** runs from Phase 1 onward — no exceptions.
- A phase's exit demo runs on `dev` compose from a clean `make up && make seed`
  — if it needs someone's laptop state, it doesn't count.
- Anything cut under time pressure is cut **horizontally** (fewer features),
  never vertically (a feature without tests/guardrails/UI states).
- LLM-dependent work always lands behind a deterministic fallback built first
  (Phase 1 rules matching, statutory engine before B2 UI) — demos must not
  depend on a model having a good day.
