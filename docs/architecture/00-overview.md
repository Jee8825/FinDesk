# 00 — System Overview

FinDesk is a full-stack agentic system. Every layer is load-bearing: remove any
one and the product breaks. This document is the map; each layer has its own
deep-dive (01–09). Feature-to-component mapping lives in
[10-module-feature-map.md](10-module-feature-map.md).

## 1. System context

```
        founders · accountants · CA firms (multi-client)
                          │  browser
                          ▼
                 ┌─────────────────┐
                 │   FRONTEND      │  Next.js 14 — books, conflict/anomaly cards,
                 │  (dashboard)    │  receivables radar, cash forecast, approvals
                 └────────┬────────┘
                          │ REST + SSE (contracts/api.yaml)
                          ▼
                 ┌─────────────────┐        ┌────────────────────────────┐
                 │   BACKEND API   │◄──────►│  APP DATA (Postgres 16)    │
                 │  FastAPI        │        │  tenants, ledger, invoices,│
                 │  auth · RBAC ·  │        │  matches, conflicts,       │
                 │  approval engine│        │  anomalies, approvals,     │
                 └────────┬────────┘        │  forecasts, audit log      │
                          │ enqueue (Redis streams)└────────────────────────────┘
                          ▼
                 ┌─────────────────┐
                 │  ORCHESTRATION  │  LangGraph: Planner → Executor → Critic
                 │  (agent runs)   │            → Approval Gate
                 └──┬────┬────┬────┘
            tools   │    │    │  guardrails (deterministic, outside LLM loop)
                    ▼    │    ▼
        ┌──────────────┐ │ ┌──────────────────┐
        │ TOOL LAYER   │ │ │ POLICY ENGINE    │  no money moves · no unapproved
        │ MCP servers: │ │ │ statutory clocks │  send · no contested commits ·
        │ bank/AA,     │ │ └──────────────────┘  45-day compliance both sides
        │ Tally, Zoho, │ │
        │ GST/IMS,     │ ▼
        │ email, TReDS │ ┌──────────────────────────────────────────┐
        └──────────────┘ │ MEMORY — Recall service (vendored)       │
                         │ episodic→semantic→procedural · decay ·   │
                         │ confidence · conflict detection ·        │
                         │ provenance (Neo4j) · budget-packed       │
                         │ retrieval (Postgres+pgvector · Redis)    │
                         └──────────────────────────────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ OBSERVABILITY   │  Langfuse + OTel GenAI spans · append-only
                 │ + AUDIT         │  audit log · eval/calibration harness
                 └─────────────────┘
```

External systems (always behind MCP tools, never called directly from agents):
bank statement files & Account Aggregator (Setu/Finvu), Tally/Zoho Books, GST
portal & IMS, e-invoice (NIC), email provider, TReDS platforms.

## 2. The layers and their single responsibility

| # | Layer | Responsibility | Must NOT do |
|---|---|---|---|
| 01 | [Orchestration](01-orchestration.md) | Decompose goals, run agent state machines, route to approval | Call vendors directly; embed policy in prompts |
| 02 | [Tool layer (MCP)](02-tools-mcp.md) | Typed, contract-bound access to external systems | Contain business logic or memory writes |
| 03 | [Memory (Recall)](03-memory-recall.md) | Beliefs: patterns, confidence, conflicts, provenance | Be the system of record for ledger facts |
| 04 | [Data & storage](04-data-storage.md) | Tenanted system of record + queues + caches | Leak across tenants; accept floats for money |
| 05 | [Guardrails](05-guardrails.md) | Deterministic policy outside the LLM loop | Be bypassable by any agent path |
| 06 | [Backend API](06-backend-api.md) | Auth, RBAC, approval workflow, REST+SSE to UI | Run LLM reasoning inline in request handlers |
| 07 | [Frontend](07-frontend.md) | Make agent work legible: cards, queues, Why-chains | Talk to anything but the backend API |
| 08 | [Observability](08-observability.md) | Trace every action; audit trail; eval harness | Store raw PII in traces |
| 09 | [Infra & deployment](09-infra-deployment.md) | Compose dev env, CI gates, environments | — |

## 3. Canonical data flow: one bank transaction

The lifecycle below is the spine of Module A; every layer appears exactly once.

1. **Ingest** — statement file lands (upload or AA pull). Tool `bank_statements`
   normalizes rows; backend writes them to the app DB with source provenance.
   An `ingestion.completed` event goes onto the Redis stream.
2. **Plan** — the reconciliation graph wakes. Planner decomposes: match
   transactions → categorize → conflict-check → anomaly-scan → report deltas.
3. **Recall before reason** — Executor retrieves per-counterparty memory
   (deduction patterns, category history, payment behavior) under a token
   budget. Example: client historically deducts 2% TDS → ₹44,100 deposit
   matches the ₹45,000 invoice; TDS entry is booked, not guessed.
4. **Critic** — a second model pass validates the match/categorization against
   memory and the books *before* anything is committed. Disagreement = route to
   human, never overwrite.
5. **Conflict check (write-time)** — proposed entry contradicts a stored
   belief? Raise a **conflict card** (both claims + confidence + hypotheses)
   and block the commit until a human resolves it with one tap. Resolution is
   written to the provenance graph and back into memory.
6. **Guardrails** — deterministic checks (no contested commit, confidence
   floor, statutory rules) run on the final action *outside* the LLM loop.
7. **Commit + learn** — entry posts to the ledger; the exchange is ingested
   into Recall (reinforces or revises beliefs); provenance edges link entry ↔
   evidence ↔ memory ↔ resolution.
8. **Trace** — every step emitted as OTel GenAI spans to Langfuse; the audit
   log gets the append-only record that powers the "Why?" button.

Module B consumes the same spine: B1 reads payment events into behavior
distributions; B3 recomputes the forecast on every ledger event; B2/B4 turn
forecast + statute into gated recommendations.

## 4. Cross-cutting invariants

- **Tenancy**: `tenant_id` (company) + acting `user_id` on every request, job,
  memory call, tool call, and span. CA-firm console = many tenants, one user,
  explicit tenant switch.
- **Money**: integer paise. **Time**: UTC storage, IST presentation.
- **Asynchrony**: user-facing reads are synchronous against the app DB; all
  agent work is queued (Redis streams) and streamed back over SSE. No LLM call
  inside a request handler.
- **Explainability**: any number on screen can answer "Why?" — the provenance
  chain (transactions → rules → memories → resolutions) is a product feature
  (A8) and the credit-room asset (B5), not a debug log.
- **Approval gate**: consequential actions (external sends, legal docs,
  payments re-timing, TReDS) exist only as *drafts* until a human approves.
  Maker-checker by construction.

## 5. Environments

| Env | Purpose | Data |
|---|---|---|
| `dev` (compose) | local full-stack | synthetic fixtures only |
| `staging` | integration + demo | anonymized/synthetic |
| `prod` | customers | real, AA-consented, encrypted at rest |

## 6. Reading order for new contributors (and their agents)

`00` (this) → your layer's doc → [10-module-feature-map.md](10-module-feature-map.md)
→ `contracts/` for everything you touch → `docs/team/agentic-coding.md`.
