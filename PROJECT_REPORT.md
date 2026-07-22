# FinDesk — Project Report

> **The Autonomous CFO for Indian SMEs.** *"It doesn't just close your books. It defends your cash."*

A full-stack, multi-agent finance-operations platform for Indian startups, SMEs and MSMEs (10–200 employees). FinDesk sits **on top of** the books a business already keeps (Tally, Zoho Books) — it does not replace them — and autonomously produces clean, conflict-free, provenance-backed books, then turns those books into cash-flow foresight and gated action.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem & Product Thesis](#2-problem--product-thesis)
3. [Feature Catalogue (A1–A8, B1–B5)](#3-feature-catalogue-a1a8-b1b5)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [Monorepo Layout](#6-monorepo-layout)
7. [Layer-by-Layer Deep Dive](#7-layer-by-layer-deep-dive)
8. [The Recall Memory Engine](#8-the-recall-memory-engine)
9. [Agentic Workflows](#9-agentic-workflows)
10. [Canonical End-to-End Workflow](#10-canonical-end-to-end-workflow-one-bank-transaction)
11. [Guardrails, Policy & Compliance](#11-guardrails-policy--compliance)
12. [Data Model & Storage](#12-data-model--storage)
13. [Contracts & Code Generation](#13-contracts--code-generation)
14. [Security, Tenancy & PII](#14-security-tenancy--pii)
15. [Observability, Audit & Evaluation](#15-observability-audit--evaluation)
16. [Infrastructure, CI/CD & Testing](#16-infrastructure-cicd--testing)
17. [Build Phases & Status](#17-build-phases--status)
18. [Core Design Principles & Invariants](#18-core-design-principles--invariants)
19. [Glossary](#19-glossary)

---

## 1. Executive Summary

FinDesk is an **agentic financial back-office** built as a monorepo of seven cooperating layers: a Next.js frontend, a FastAPI backend/control-plane, a LangGraph agent-orchestration layer, an MCP tool layer, a vendored **Recall** living-memory engine, a shared contracts/codegen layer, and infrastructure/observability.

The defining architectural stance is **trust by construction**:

- The agent **never moves money** — no payment capability exists anywhere in the codebase.
- The agent **never sends external communication or files anything legal** without an explicit human approval — everything consequential is *draft-only* behind an **approval gate**.
- Every consequential action is validated by a chain of independent checkers — a **Critic model**, then a **deterministic policy engine outside the LLM loop**, then a **human**. This is maker-checker control by design.
- Every number on screen can answer **"Why?"** via a provenance chain (transactions → rules → memories → resolutions), backed by an append-only, hash-chained audit log.

The product is organized in two modules: **Module A (Bookkeeping Foundation)** produces trustworthy books; **Module B (Cash Command Layer)** turns them into foresight and MSME-compliant action. All 13 spec features (A1–A8, B1–B5) are implemented across build Phases 0–6.

---

## 2. Problem & Product Thesis

Indian SMEs run on books that are perpetually behind, inconsistently categorized, and riddled with reconciliation ambiguity (TDS deductions, partial payments, bank fees). Meanwhile the **MSME Development Act (2006)** gives them statutory rights (payment within 45 days of acceptance; 3× RBI bank-rate compound interest on default) that they almost never enforce, and cash-flow visibility is a spreadsheet at best.

FinDesk's thesis:

| Module | Promise | How |
|---|---|---|
| **A — Bookkeeping Foundation** | *Save money.* Clean, conflict-free, provenance-backed books with near-zero manual reconciliation. | Autonomous, memory-driven reconciliation + categorization; write-time conflict detection; anomaly ("found money") cards; explainable reports. |
| **B — Cash Command Layer** | *Save the business.* Turn books into foresight and enforce cash rights. | Per-counterparty payment-behavior prediction; MSME 45-day statutory enforcement; living 4/13-week scenario forecasts; TReDS working-capital actions; a credit-ready data room. |

Target user: founders, in-house accountants, and CA firms operating a **multi-client console** (one CA user, many tenants).

---

## 3. Feature Catalogue (A1–A8, B1–B5)

### Module A — Bookkeeping Foundation
| ID | Feature | What it does |
|---|---|---|
| **A1** | Ingestion | Statement upload / Account-Aggregator pull / Tally & Zoho export import; normalized, hash-deduped transactions with source provenance; historical seeding into memory on onboarding. |
| **A2** | Autonomous reconciliation | Matches transactions ↔ invoices/bills, including **TDS-adjusted** matches (e.g. ₹44,100 deposit ↔ ₹45,000 invoice with 2% TDS), partial payments and bank fees, using learned per-counterparty deduction patterns. |
| **A3** | Categorization with consistency | Consistent chart-of-accounts categorization anchored by crystallized vendor-category beliefs (the agent stops second-guessing settled mappings). |
| **A4** | Cross-period conflict detection | Write-time detection when a proposed entry contradicts a stored belief → a **conflict card** (both claims + confidence + hypotheses) blocks the commit until a human resolves it in one tap. |
| **A5** | Critic self-correction | An independent second model pass re-derives every match/categorization and checks it against memory and the ledger before commit. The accuracy moat, measured in CI. |
| **A6** | Anomaly detection | Per-vendor behavioral baselines flag duplicates, overcharges, and out-of-pattern spend as cards with recoverable-money flags. |
| **A7** | Receivables chasing | Tone-calibrated collection drafts per client, **gated** email send. |
| **A8** | Reporting + "Why?" | Month-end pack and GST summary where every figure drills into its full evidence trail. |

### Module B — Cash Command Layer
| ID | Feature | What it does |
|---|---|---|
| **B1** | Payment-behavior memory | Learns each client's promise-vs-actual latency and detects worsening-trend **drift** ("8 → 15 → 22 days"). |
| **B2** | 45-Day Enforcer | Deterministic MSME statutory clock per receivable **and** payable; accrued compound interest; escalation ladder (nudge → reminder → Act letter → Samadhaan prep), all prepared, never filed. |
| **B3** | Living cash forecast | Versioned 4/13-week base/upside/downside scenarios with confidence bands and gap attribution, recomputed on every ledger event. |
| **B4** | Working-capital actions | Ranked, costed options (TReDS discounting / collect / re-time) behind approvals, with a buyer-side 45-day-compliance guardrail. |
| **B5** | Credit-ready data room | Provenance graph exported as a lender-ready data room, a **FinDesk Score** from provenance coverage, and verifiable audit-chain share links. |

---

## 4. System Architecture

### 4.1 One-page view

```
        founders · accountants · CA firms (multi-client)
                          │  browser
                          ▼
                 ┌─────────────────┐
                 │   FRONTEND      │  Next.js 14 — books, conflict/anomaly cards,
                 │  (dashboard)    │  receivables radar, cash forecast, approvals
                 └────────┬────────┘
                          │ REST + SSE  (contracts/api.yaml → generated client)
                          ▼
                 ┌─────────────────┐        ┌────────────────────────────┐
                 │   BACKEND API   │◄──────►│  APP DATA (Postgres 16)    │
                 │  FastAPI        │        │  tenants, ledger, invoices,│
                 │  auth · RBAC ·  │        │  matches, conflicts,       │
                 │  approval engine│        │  anomalies, approvals,     │
                 └────────┬────────┘        │  forecasts, audit log      │
                          │ enqueue (Redis streams)  └───────────────────┘
                          ▼
                 ┌─────────────────┐
                 │  ORCHESTRATION  │  LangGraph: Planner → Executor → Critic
                 │  (agent runs)   │            → Approval Gate
                 └──┬────┬────┬────┘
            tools   │    │    │  guardrails (deterministic, OUTSIDE the LLM loop)
                    ▼    │    ▼
        ┌──────────────┐ │ ┌──────────────────┐
        │ TOOL LAYER   │ │ │ POLICY ENGINE    │  no money moves · no unapproved
        │ MCP servers  │ │ │ statutory clocks │  send · no contested commit ·
        │ (bank, email,│ │ └──────────────────┘  45-day compliance both sides
        │  TReDS, …)   │ ▼
        └──────────────┘ ┌──────────────────────────────────────────┐
                         │ MEMORY — Recall service (vendored)       │
                         │ episodic→semantic→procedural · decay ·   │
                         │ confidence · conflict detection ·        │
                         │ provenance (Neo4j) · budget-packed       │
                         │ retrieval (Postgres+pgvector · Redis)    │
                         └──────────────────────────────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ OBSERVABILITY   │  Langfuse + OTel GenAI spans · append-only
                 │ + AUDIT         │  hash-chained audit log · eval harness
                 └─────────────────┘
```

### 4.2 Layers & single responsibilities

| # | Layer | Responsibility | Must **not** do |
|---|---|---|---|
| 01 | Orchestration (LangGraph) | Decompose goals, run agent state machines, route to approval | Call vendors directly; embed policy in prompts |
| 02 | Tool layer (MCP) | Typed, contract-bound, tenant-scoped access to external systems | Contain business logic or memory writes |
| 03 | Memory (Recall) | Beliefs: patterns, confidence, conflicts, provenance | Be the system of record for ledger facts |
| 04 | Data & storage | Tenanted system of record + queues + caches | Leak across tenants; accept floats for money |
| 05 | Guardrails | Deterministic policy outside the LLM loop | Be bypassable by any agent path |
| 06 | Backend API | Auth, RBAC, approval workflow, REST + SSE | Run LLM reasoning inline in request handlers |
| 07 | Frontend | Make agent work legible: cards, queues, Why-chains | Talk to anything but the backend API |
| 08 | Observability | Trace every action; audit trail; eval harness | Store raw PII in traces |
| 09 | Infra & deployment | Compose dev env, CI gates, environments | — |

---

## 5. Technology Stack

### 5.1 By layer
| Concern | Technology |
|---|---|
| **Orchestration / agents** | **LangGraph** state machines, Python 3.11+, async workers over Redis Streams; provider-abstracted heavy/light LLM roles (no vendor SDK in node code) |
| **Backend / API** | **FastAPI**, Pydantic v2, SQLAlchemy 2 (async), Alembic, Uvicorn; JWT + argon2 + optional TOTP; Server-Sent Events (SSE) |
| **App database** | **PostgreSQL 16** (system of record), integer-paise money, UUIDv7 keys, row-level security in prod |
| **Memory engine (Recall)** | FastAPI service; **PostgreSQL 16 + pgvector** (units + embeddings, HNSW cosine), **Neo4j 5** (provenance graph), **Redis 7** (working memory / prefetch); pluggable LLM/embedding providers (Qwen default; OpenAI/Anthropic/local) |
| **Tools** | **Model Context Protocol (MCP)** servers, typed schemas mirroring contracts, per-tenant credentials, idempotent writes |
| **Queue / cache** | **Redis 7** — Streams for agent jobs, pub/sub → SSE bridge, short-lived caches, idempotency keys |
| **Frontend** | **Next.js 14** (App Router), TypeScript, **Tailwind CSS**, **shadcn/ui**, **TanStack Query**, generated typed API client |
| **Observability** | **Langfuse** + **OpenTelemetry** (GenAI semantic conventions); append-only hash-chained audit log; eval/calibration harness |
| **Infra / DevOps** | **Docker Compose** (dev), **GitHub Actions** CI (paths-filtered), object storage (S3-compatible), cloud secret manager in prod |

### 5.2 Cross-cutting conventions
- **Money:** integer **paise** (`amount_paise`, `BIGINT`) — never floats.
- **IDs:** UUIDv7 strings (time-sortable), one `run_id`/`step_id`/`tenant_id` join key across all layers.
- **Time:** timezone-aware **UTC** in storage; **IST** only at the presentation edge.
- **Prompts:** every LLM prompt lives in `prompts/`, loaded by name+version — no inline prompt strings.
- **SQL:** confined to repository modules; engine/agent code is ORM-free and provider-agnostic.
- **Quality gates:** ruff + mypy (Python), eslint + tsc (TypeScript), conventional commits.

---

## 6. Monorepo Layout

| Path | What lives here |
|---|---|
| `frontend/` | Next.js 14 dashboard (books, forecast, radar, approvals, data room) |
| `backend/` | FastAPI app: auth, REST + SSE API, services, approval engine, guardrails |
| `agents/` | LangGraph orchestration: Planner → Executor → Critic → Approval Gate; the stream worker |
| `tools/` | MCP tool servers (bank statements, ledger import, email, TReDS) |
| `memory/` | **Recall** living-memory engine (vendored copy, FinDesk-tuned) |
| `shared/` | Cross-layer types + **generated** contract models (Python + TypeScript) |
| `contracts/` | Versioned API / tool / memory / DB / event contracts — **the source of truth** |
| `prompts/` | Every LLM prompt in the system (none hardcoded) |
| `infra/` | Docker, CI/CD, observability + eval config |
| `docs/` | Architecture deep-dives (00–10), team process, ADRs, product spec |
| `scripts/` | Seed data, contract generation, smoke tests, offboarding purge |

Actual implemented scale: **8 agent graph packages**, **12 backend API routers**, **12 Alembic migrations**, **4 MCP tool servers**, a vendored **15-module Recall core**, and a Next.js app of ~13 pages.

---

## 7. Layer-by-Layer Deep Dive

### 7.1 Orchestration (`agents/`)
A set of **LangGraph state machines** executed by a **stateless stream worker** (`worker.py`) consuming Redis Streams (`agents:interactive`, `agents:batch`). The worker maps a job event prefix (`job.reconciliation.`, `job.anomaly_scan.`, `job.collections.`, `job.forecast.`, `job.working_capital.`, `job.enforcer_tick.`, `job.ping.`) to a graph + typed state factory, injects shared `BackendClient` / `MemoryClient` handles, and runs the graph.

Core pattern per step: **recall before reason** — retrieve budget-packed memory context first, act only through MCP tools, propose a result, then let the Critic independently re-derive it. Consequential actions are *structurally* routed to the Approval Gate (a graph state, not a prompt instruction). LangGraph checkpoints serialize to Postgres so an interrupted run (approval wait, crash, deploy) resumes exactly where it paused. At-least-once delivery + idempotent steps (each step checks `step_id` before re-applying side effects). Model roles (`heavy` for plan/execute/critic, `light` for scoring/compression) sit behind a provider protocol in `llm.py`.

### 7.2 Tool layer (`tools/`)
All outside-world access goes through **MCP servers**: typed, contract-bound, tenant-scoped, loaded on demand to preserve context budget. Tools are pure plumbing — no business logic, no prompts, no memory writes. Implemented servers: `bank_statements` (CSV/PDF/XLS → normalized transactions), `ledger_import` (Tally/Zoho export parser), `email` (sandbox draft+send), `treds` (sandbox listing/quote). Contract-defined for expansion: account-aggregator, GST/IMS, e-invoice. Every amount is integer paise, every record carries `source` provenance, all writes are idempotent (`run_id:step_id:n`). **Outbound side effects require an `approval_token` minted by the backend** — a tool physically refuses a consequential call without one, so even a compromised prompt cannot send mail.

### 7.3 Memory (`memory/`) — Recall
A vendored **living-memory engine** running as its own service with its own datastores. Full detail in [§8](#8-the-recall-memory-engine). Agents/backend reach it only over HTTP (never its DBs). FinDesk's extension surface is limited to finance-specific prompts, typed claim kinds, conflict export, historical seeding, and provider config; core decay/confidence/conflict math is change-gated by ADR.

### 7.4 Data & storage (`backend/app/db`, memory service)
Four stores, four jobs: the **app Postgres** is the system of record for *facts*; Recall's Postgres+pgvector/Neo4j hold *beliefs* and *evidence*; **Redis** moves *work*. Every app table carries `tenant_id`; books rows are never hard-deleted; object storage (S3-compatible, tenant-prefixed, encrypted) holds documents/reports with ≥8-year retention. Tenant offboarding is one audited script: app purge + Recall atomic deletion + object-storage prefix delete + provenance cascade.

### 7.5 Guardrails (`backend/app/guardrails`, `agents/policies`)
Deterministic policy **outside the LLM loop** (NeMo-Guardrails pattern). Six non-negotiable policies (P1–P6, see [§11](#11-guardrails-policy--compliance)), a pure statutory clock engine, per-action-class confidence floors, and prompt-injection posture (ingested docs/emails are *data, never instructions*). Every verdict (pass/veto + rule id) is recorded on the approval row and the trace.

### 7.6 Backend API (`backend/`)
FastAPI: the only thing the frontend talks to and the control plane for all agent work. **No LLM call ever runs in a request handler** — the backend enqueues jobs and returns `202 + run_id`, then streams progress over SSE. Structure: thin routers → services (own transactions) → repositories (own SQL). 12 routers cover auth/tenancy, books, agent control + SSE, the human queues (conflicts, anomalies, approvals), cash (forecast, radar, wc-actions), explainability (`/why`), data room, and internal webhooks. The **approval engine** is a per-approval state machine (`requested → pending → approved|rejected|expired`) that mints single-use, hash-bound, TTL'd tokens and resumes parked runs.

### 7.7 Frontend (`frontend/`)
Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui. Its job is to make autonomous work **legible and controllable** — every agent conclusion arrives as a card with evidence and a decision affordance, and any number answers "Why?". Server Components for reads; TanStack Query against the **generated** API client (handwritten fetch shapes banned to prevent contract drift); one `useRunStream(runId)` SSE hook renders live agent progress; money rendered from integer paise via a single `formatINR` util. Signature surfaces: conflict card, forecast bands, 45-day radar, approval queue, and the Why? drawer.

### 7.8 Observability (`infra/observability`)
Three deliberately separated artifacts: **Traces** (Langfuse/OTel, TTL'd), **Audit log** (Postgres, immutable, hash-chained), **Provenance** (Neo4j, grows, atomic-delete). See [§15](#15-observability-audit--evaluation).

### 7.9 Infra (`infra/`, `.github/workflows`)
`make up` boots the whole stack (app compose + memory compose). Paths-filtered GitHub Actions CI builds layers independently; a nightly eval workflow guards accuracy. See [§16](#16-infrastructure-cicd--testing).

---

## 8. The Recall Memory Engine

Recall is FinDesk's intelligence differentiator: **memory that decays, reinforces, self-organizes, and reasons about its own beliefs**, rather than accumulating forever. It sits *above* the agent framework as a standalone FastAPI service.

### 8.1 Two axes, three tiers, two LLM roles
- **Tiers:** `episodic` (raw events, short TTL) → `semantic` (durable facts) → `procedural` (crystallized workflows), promoted by consolidation passes.
- **Strength axis (decay):** retrieval priority follows an Ebbinghaus curve `S(t) = S₀·e^(−λt)`, per-tier λ (episodic ~2-day half-life, semantic ~35-day, procedural ~2-year). Reinforced on every retrieval (×1.25, capped at 1.0, decay clock reset); tombstoned below τ = 0.05.
- **Confidence axis (epistemic):** how much to *trust* a belief. Corroboration raises with diminishing returns; contradiction lowers proportionally; dormancy drifts down; **crystallization ≥ 0.95** freezes settled knowledge.
- **LLM roles:** `heavy` (extract / consolidate / resolve conflicts) + `light` (score / compress / classify intent).

### 8.2 Core modules (`memory/recall/core`)
`decay`, `confidence`, `conflict`, `consolidation`, `ingestion`, `retrieval`, `prefetch`, `provenance`, `scoping`, `repository` (all SQL), `engine` (façade), `types`. Design rules: all prompts in `prompts/`, all SQL in `repository.py`, engine depends on provider *protocols* (never a concrete SDK), provenance (Neo4j) writes are best-effort and never block a memory write.

### 8.3 Key mechanisms
- **Write-time conflict detection:** on ingesting a semantic fact, Recall finds the nearest existing belief (pgvector cosine) within a distance threshold; the heavy LLM resolves it as `auto_resolved` / `merged` / `flagged`, retiring superseded beliefs and logging every resolution to a permanent `conflict_log` + the provenance graph.
- **Budget-packed retrieval:** candidates are scored `relevance × recency × strength` and greedily packed into an explicit token budget, compressing lower-ranked memories with the light LLM to fit more signal.
- **Predictive prefetch:** a light model classifies recent turns into a likely memory *cluster* and warms a Redis cache before the formal query, tracking hit-rate.
- **Consolidation pass:** tombstone sweep, compaction, **dormancy drift + crystallization**, and **procedural extraction** (repeated tool-call workflows detected via n-gram mining become Tier-3 memories).
- **Provenance graph (Neo4j):** every belief → its evidence chain (sessions, documents, resolutions) with `SUPPORTS`/`CONTRADICTS`/`RESOLVED_FROM` edges, powering the "Why?" endpoint and GDPR-style atomic deletion.

### 8.4 FinDesk identity mapping & claim taxonomy
| Recall field | FinDesk meaning |
|---|---|
| `tenant_id` | company |
| `user_id` | scope key: `vendor:<id>`, `client:<id>`, `user:<id>`, `tenant:global` |
| `session_id` | agent `run_id` (or `seed:<batch>` for historical seeding) |

Typed beliefs (`claim_kind` metadata): `vendor_category`, `deduction_pattern`, `payment_behavior`, `behavior_drift`, `tone_preference`, `anomaly_baseline`, `workflow`. Retrieval budgets are set per graph node (e.g. reconciliation.match = 800 tokens, forecast.distributions = 1200).

### 8.5 API surface
`POST /memory/ingest`, `POST /memory/retrieve`, `GET /memory/{id}/why`, `GET /memory/user-owned` (GDPR), `DELETE /memory/{id}` (tenant-scoped cascade), `POST /memory/promote` (scope promotion), `POST /memory/prefetch`, `POST /admin/consolidate`, `GET /conflicts`, `GET /stats`. Cross-tenant isolation is enforced at the service (not only via the backend in front of it).

---

## 9. Agentic Workflows

### 9.1 The core pattern: Planner → Executor → Critic → Approval Gate

```
 goal ──► PLANNER ──► plan: [step₁ … stepₙ]         (heavy model; plan is data, replayable)
              │
              ▼  (per step)
          EXECUTOR ── recall(memory) ── act(MCP tools) ── propose result   (recall before reason)
              │
              ▼
           CRITIC ── independent re-derivation vs memory + ledger          (the accuracy moat, A5)
              │
        ┌─────┴─────────┐
        ▼               ▼
   guardrails OK    disagreement / low confidence / contested / consequential
        │               │
        ▼               ▼
     COMMIT        APPROVAL GATE ──► human queue (frontend) ──► resume graph
```

- **Planner** decomposes a goal into typed steps with declared tool needs and memory scopes. Plans are logged data, not prose.
- **Executor** performs one step: recall budget-packed memory first, then act through MCP tools only.
- **Critic** (separate pass, ideally different model config) re-derives the conclusion independently; disagreement routes to a human — it never overwrites.
- **Approval Gate** is a LangGraph checkpoint+interrupt; a human decision arriving via the backend resumes the run.

### 9.2 Graph catalogue (implemented)

| Graph | Trigger | Node flow (actual) | Consequential action |
|---|---|---|---|
| `reconciliation` | ingestion.completed / nightly | `fetch_and_parse → ingest → match → categorize → critic → commit → learn` | commits ledger entries (gated by conflict/confidence) |
| `anomaly_scan` | post-reconciliation / on-demand | baseline recall → scan → rank → card | none (cards only) |
| `collections` | daily | overdue scan → tone recall → draft emails | external send (always gated) |
| `enforcer` (45-day) | daily clock tick | statutory state → interest calc → escalation step → draft Act letter | letters/Samadhaan docs (draft-only, gated) |
| `cash_forecast` | every ledger event (debounced) | B1 distributions → 3 scenarios → gap attribution | none (alerts only) |
| `working_capital` | forecast gap detected | option pricing (TReDS/collect/re-time) → rank | every action recommend-only, gated |
| `ping` | manual / smoke | no-op step writing run/step rows | none (integration proof) |

Each graph lives in `agents/findesk_agents/graphs/<name>/` with `graph.py` (wiring only), `nodes.py`, `state.py` (typed Pydantic LangGraph state), and per-node helper modules (`matching.py`, `categorization.py`, `detection.py`, `engine.py`, `drafting.py`, `letters.py`, `options.py`). Month-end close (A8) composes reconciliation + anomalies + report generation via the backend reports service.

### 9.3 The learning loop
After a committed exchange, the reconciliation `learn` node ingests the outcome back into Recall — reinforcing or revising beliefs (payment-behavior observations, deduction patterns, vendor categories) — and provenance edges link entry ↔ evidence ↔ memory ↔ resolution. The system gets smarter every reconciliation without agent-code changes.

---

## 10. Canonical End-to-End Workflow (one bank transaction)

The spine of Module A — every layer appears exactly once:

1. **Ingest** — a statement file lands (upload or AA pull); the `bank_statements` tool normalizes rows; the backend writes them with source provenance and emits `ingestion.completed` onto a Redis stream.
2. **Plan** — the reconciliation graph wakes; the Planner decomposes: match → categorize → conflict-check → anomaly-scan → report deltas.
3. **Recall before reason** — the Executor retrieves per-counterparty memory under a token budget. *Example:* a client historically deducts 2% TDS → a ₹44,100 deposit matches a ₹45,000 invoice; the TDS entry is **booked, not guessed**.
4. **Critic** — a second model pass validates the match/categorization against memory and the books *before* commit. Disagreement → human, never overwrite.
5. **Conflict check (write-time)** — if the proposed entry contradicts a stored belief, a **conflict card** (both claims + confidence + hypotheses) blocks the commit until a human resolves it in one tap; the resolution flows to the provenance graph and back into memory.
6. **Guardrails** — deterministic checks (no contested commit, confidence floor, statutory rules) run on the final action *outside* the LLM loop.
7. **Commit + learn** — the entry posts to the ledger; the exchange is ingested into Recall; provenance edges are written.
8. **Trace** — every step is emitted as OTel GenAI spans to Langfuse; the append-only audit log records the row that powers the "Why?" button.

Module B consumes the same spine: B1 reads payment events into behavior distributions; B3 recomputes the forecast on every ledger event; B2/B4 turn forecast + statute into gated recommendations.

---

## 11. Guardrails, Policy & Compliance

### 11.1 The non-negotiables (hard policies)
| # | Policy | Enforcement point |
|---|---|---|
| **P1** | **Never move money.** No payment-initiation capability exists anywhere. | Capability absence — the strongest guardrail: the tool doesn't exist. |
| **P2** | **Never send external comms unapproved.** Email/TReDS/letters are draft-only until an `approval_token` exists. | Tool servers refuse without a token; backend mints tokens only from human decisions. |
| **P3** | **Never commit a contested or low-confidence entry.** | Commit service checks open conflict / confidence floor before ledger write. |
| **P4** | **Never breach our own 45-day obligations.** Payables re-timing must keep MSME-vendor payables inside statutory limits. | Statutory clock engine veto on `wc_actions`. |
| **P5** | **Tenancy isolation.** No cross-tenant read/write anywhere. | RLS + tool-server scoping + memory tenant keys. |
| **P6** | **Legal-adjacent framing.** Interest computations and Samadhaan docs are *preparations*, flagged "review with your CA"; the system never files. | Document templates + UI copy + absence of any filing tool. |

Policies are versioned data compiled into the enforcement engine; a policy change requires an ADR + dual review.

### 11.2 Maker–checker by construction
**Maker** = Executor (drafts) · **Checker #1** = Critic (model) · **Checker #2** = policy engine (deterministic) · **Checker #3** = human approval. The approval queue is the *only* path to an `approval_token`; tokens are single-use, action-hash-bound, and expiring.

### 11.3 Statutory clock engine (pure, no LLM)
Implements the **MSME Development Act** §15 (payment ≤ 45 days from acceptance) and §16 (compound interest **with monthly rests** at 3× RBI bank rate on default). Deterministic to the paisa (integer paise, half-up rounding), test-vectored, with a fixed escalation ladder (`none → nudge → reminder → act_letter → samadhaan_prep`). The agent only chooses **wording within a state**, never the state-transition rules.

### 11.4 Confidence floors (examples)
Auto-commit a match requires *crystallized or ≥ 0.90 + Critic agreement*; auto-booking a TDS-adjusted match requires *≥ 0.85 + pattern seen ≥ 3 times*; a high-severity anomaly requires *≥ 2 independent signals*. Below floor → approval queue with evidence attached. Floors live in policy YAML, not prompts.

### 11.5 Kill switches
Per-tenant `agent_paused` (drains queues, freezes commits) and a global read-only mode for incident response — both one `make` target away and audited.

---

## 12. Data Model & Storage

App Postgres schema (12 Alembic migrations), grouped:

- **Identity & tenancy:** `tenants` (GSTIN, Udyam MSME registration, entity tree), `users`, `memberships` (RBAC: `owner` / `accountant` / `ca` / `viewer`; a CA holds memberships across many tenants), `counterparties` (unified vendor/client master, MSME status driving 45-day obligations *both ways*, TDS defaults).
- **Books (Module A):** `bank_accounts`, `bank_transactions` (hash-deduped, source provenance), `invoices` (AR), `bills` (AP), `expenses`, `matches` (type `full|partial|fee|tds_adjusted`, confidence, matched-by, critic verdict), `ledger_entries` (committed double-entry), `conflicts` (both claims + confidence + hypotheses + resolution + memory backref), `anomalies` (typed cards + recoverable-money flag).
- **Cash (Module B):** `payment_observations`, `statutory_clocks` (per-receivable/payable 45-day state machine + accrued compound interest), `forecasts` + `forecast_lines` (versioned base/upside/downside), `wc_actions` (ranked options).
- **Control plane:** `approvals` (queue + token issuance), `agent_runs` + `agent_steps` (registry + LangGraph checkpoints), `audit_log` (insert-only, hash-chained), `documents` (object-storage metadata; bytes never in Postgres).

Conventions: UUIDv7 PKs, `BIGINT` paise, UTC timestamps, soft deletes only where a regulator expects history. Redis holds job streams, the pub/sub→SSE bridge, and short-lived caches — nothing durable lives only in Redis.

---

## 13. Contracts & Code Generation

`contracts/` is the **source of truth** for every cross-layer shape: `api.yaml` (OpenAPI), `tools.md`, `memory.md`, `db.md`, `events.md`. A generator (`scripts/gen_contracts.py`, `make contracts`) produces:
- `shared/py/` — Pydantic models + `api_paths.py` (imported by the backend; never redeclared).
- `shared/ts/` — a typed API client + `api-paths.ts` (imported by the frontend).

**Contract-first is a hard rule:** any change to a request/response/tool/event shape updates `contracts/` in the same PR and regenerates `shared/`; CI fails on drift. Tool output schemas are versioned (`tool_name@v2`) — changing one without a version bump is "the single most-banned action in the repo." This lets the frontend build against generated types with mocked responses and swap to real endpoints the day they exist — the contract, not a meeting, is the synchronization point.

---

## 14. Security, Tenancy & PII

- **AuthN/Z:** short-lived JWT access + rotating refresh, argon2 hashing, optional TOTP. RBAC roles resolve `(user_id, tenant_id, role)` on every request; the tenant comes from the token's active-tenant claim — **never a query param**. Approval decisions re-verify role *and* re-hash the action payload against the token request (no approve-then-mutate).
- **Tenancy:** `tenant_id` on every request, job, memory call, tool call, and span. Row-level security in prod + tool-server-side scoping + memory tenant keys — defense in depth. A CA console is many tenants under one user with explicit tenant switching.
- **Prompt-injection posture:** ingested documents/emails are **data, never instructions** (delimited, role-isolated); third-party text is marked `untrusted=true` and never enters system prompts; consequential actions can't be content-triggered anyway (P2 token requirement).
- **PII discipline:** external observability holds **references, not payloads** (redaction in a shared SDK wrapper, not per-developer); no real financial data in fixtures/logs/traces; derived beliefs deletable per tenant atomically.

---

## 15. Observability, Audit & Evaluation

| Artifact | Question it answers | Store | Mutability |
|---|---|---|---|
| **Traces** | what did the system do, step by step, how long, how much | Langfuse (OTel) | TTL'd |
| **Audit log** | what happened to the books/actions, attributable to whom | Postgres | immutable, insert-only, hash-chained |
| **Provenance** | why is this belief/number held | Neo4j (memory service) | grows, atomic-delete |

- **Tracing:** every agent run is a root trace with spans for plan/step/tool-call/memory-call/critic/policy-verdict; model spans carry token counts, latency, cost, prompt name+version — never the raw payload (reference pattern). One `run_id`/`step_id`/`tenant_id` join key spans backend, agents, tools, and memory.
- **Audit log:** written via a DB role with no UPDATE/DELETE; rows hash-chained (`row_hash = H(prev_hash ‖ payload)`); records ledger commits, resolutions, approval decisions + token ids, external sends, policy verdicts, config changes, kill-switch flips, data exports. This is the credit-room asset (B5) and a beyond-SOC-2 audit trail.
- **Eval harness** (`infra/observability/evals`, CI nightly + pre-release): reconciliation precision/recall, Critic uplift (A5), categorization consistency (A3), conflict quality (A4), forecast calibration (B3), payment-prediction MAE (B1). Calibration results are **published in-product** — trust is the pitch, so the eval output is a customer-facing, versioned artifact.

---

## 16. Infrastructure, CI/CD & Testing

### 16.1 Dev environment
`make up` boots the whole stack from two compose files (app stack + memory stack) with hot reload everywhere; `make seed` loads a synthetic SME (vendors, clients, ~6 months of transactions, deliberate anomalies + conflicts) so every layer renders something real.

Default ports — backend `8080`, frontend `3001`, app-postgres `5433`, app-redis `6380`, recall-api `8000`, recall dashboard `3000`, recall-postgres `5432`, neo4j `7474/7687`, recall-redis `6379`; collisions remapped via a gitignored `docker-compose.override.yml`.

### 16.2 CI (GitHub Actions)
Paths-filtered so layers build independently: **secrets hygiene** (no committed `.env`) → **lint** (ruff + mypy; eslint + tsc) → **contracts drift** (regenerate `shared/`, fail on diff) → **unit** (pytest per workspace, vitest/jest frontend) → **build** (docker + next build) → **integration** (label-gated/nightly testcontainers) → **evals** (nightly accuracy/calibration; regression = red). `main`/`dev` protected; 1 CODEOWNER review + green checks; conventional-commit titles enforced.

### 16.3 Testing strategy
Pure logic → `tests/unit`; anything needing datastores → `tests/integration` (testcontainers, marked `integration`). Agent nodes are pure-tested with fake tool/memory clients; whole graphs run against recorded fixtures; the statutory engine ships with paisa-exact test vectors. LLM-dependent work always lands **behind a deterministic fallback built first** (Phase-1 rules matching, statutory engine before B2 UI) — demos never depend on a model having a good day.

### 16.4 Environments & DR
`dev` (compose, synthetic) → `staging` (integration/demo, anonymized) → `prod` (managed Postgres+Redis, object storage, secret manager; **India region for data residency**). Images built once on merge, promoted by tag; migrations run as a release step. Nightly logical backups + PITR for both Postgres instances, Neo4j dumps, object-storage versioning; quarterly restore drill.

---

## 17. Build Phases & Status

Built as **vertical slices, not horizontal layers** — a phase is done when a user can *do* something end-to-end on `dev` compose. Backend leads the dependency chain (contracts → DB → API → graphs); frontend builds against the contract-generated client and swaps to real endpoints when they exist.

| Phase | Delivered |
|---|---|
| **P0 — Skeleton** | `make up` boots everything; contract generator + CI hard-fail; FastAPI factory + JWT; worker + no-op `ping` graph; Recall stack + smoke; Next.js shell + `useRunStream`. Exit: log in, run ping, watch live SSE. |
| **P1 — Walking skeleton** | Statement upload → `bank_statements` parse → deduped rows; **rules-only** reconciliation v0 (no LLM) with real commit service; memory wired (payment_behavior observations); audit log + Why? v0. |
| **P2 — Module A core** | LLM/**TDS-aware** matching + `deduction_pattern` learning; A3 categorization + crystallization; real Critic (A5); A4 write-time conflict cards + one-tap resolution; approval engine + hash-bound tokens + guardrail v1; eval harness v1. |
| **P3 — Module A complete** | A6 anomaly scan + found-money cards; A7 collections with gated email; A8 month-end pack + polished Why? drawer. |
| **P4 — Module B** | B1 payment behavior + drift; **B2 statutory clock engine + radar**; B3 scenario forecast + calibration eval; B4 working-capital actions + gated TReDS + P4 guardrail; B5 data room + FinDesk Score + verifiable audit chain. |
| **P5 — A1 hardening** | Tally/Zoho export import + onboarding historical seeding; integration test suite (spec complete). |
| **P6 — Audit hardening** | Backend correctness, error hardening, and optimization across all layers; memory-layer confidence-dynamics + tenant-scope fixes (ADR-0003). |

**Result:** all 13 spec features (A1–A8, B1–B5) implemented; external integrations that require live third-party access (email send, TReDS listing, AA pull) run as sandboxes/fixtures for the hackathon while the contracts and gating are production-shaped.

---

## 18. Core Design Principles & Invariants

1. **Trust is the product.** Guardrails are deterministic code outside the LLM loop; an agent cannot talk its way past them and a prompt injection cannot disable them.
2. **Maker-checker by construction.** Model → deterministic policy → human. The approval gate is a graph *state*, not a prompt instruction.
3. **Recall before reason.** Every executor step retrieves budget-packed memory before acting.
4. **Facts vs beliefs.** The app DB is the exact system of record (amounts, dates); memory holds *beliefs about patterns*. If a number must be exact, it's read from the DB, not memory.
5. **Contract-first.** Shapes change in `contracts/` before the code that depends on them; `shared/` is generated, never hand-edited.
6. **Explainability is a feature.** Any on-screen number answers "Why?" via a real provenance chain — the A8 button and B5 credit asset, not a debug log.
7. **Tenancy everywhere; money in paise; time in UTC.** Non-negotiable, on every request/job/call/span.
8. **Deterministic fallback first.** LLM work always lands behind a deterministic path built earlier, so accuracy problems are attributable to reasoning, not plumbing.

---

## 19. Glossary

| Term | Meaning |
|---|---|
| **Module A / B** | Bookkeeping Foundation / Cash Command Layer. |
| **A1–A8 / B1–B5** | The 13 product features (see [§3](#3-feature-catalogue-a1a8-b1b5)). |
| **Recall** | The vendored living-memory engine (`memory/`). |
| **Crystallization** | Locking a high-confidence belief (≥ 0.95) so decay/drift stop. |
| **Conflict card** | A write-time contradiction surfaced for one-tap human resolution (A4). |
| **Approval token** | Single-use, action-hash-bound, TTL'd token minted only from a human approval — the physical gate on consequential actions. |
| **Statutory clock** | The MSME Act 45-day state machine + compound-interest engine (B2). |
| **TReDS** | Trade Receivables Discounting System — regulated invoice-financing platforms (B4). |
| **Samadhaan** | The MSME dispute-resolution mechanism; FinDesk *prepares* filings, never files. |
| **AA** | Account Aggregator — India's consent-based financial-data-sharing framework. |
| **Maker-checker** | The finance control pattern of separating who proposes from who approves. |
| **Provenance chain** | transactions → rules → memories → resolutions — the evidence trail behind any number. |

---

*Generated as a structured overview of the FinDesk codebase and its architecture documentation. Authoritative detail lives in `docs/architecture/` (00–10), `contracts/`, and `docs/decisions/` (ADRs).*
