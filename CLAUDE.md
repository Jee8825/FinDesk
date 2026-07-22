# CLAUDE.md — FinDesk AI Context

Runtime context for AI coding agents working on this repo. Every team member's
agent (Claude Code, Cursor, etc.) loads this file at session start. Layer
folders have their own `CLAUDE.md` with deeper, scoped rules — read the one for
the layer you are touching.

## What this is

FinDesk — the **autonomous CFO for Indian SMEs**. Two modules: **A**
(autonomous bookkeeping: ingestion, TDS-aware reconciliation, categorization,
conflict detection, anomalies, receivables chasing, explainable reports) and
**B** (cash command: payment-behavior memory, MSME Act 45-day enforcement,
scenario cash forecast, TReDS working-capital actions, credit data room).
Full spec: `docs/product/FinDesk_Product_Build_Specification.pdf`.

## Stack

- Orchestration: **LangGraph** (Planner → Executor → Critic → Approval Gate), Python 3.11+
- Backend: **FastAPI** + Pydantic v2 + SQLAlchemy 2 (async) + Alembic, Postgres 16
- Memory: **Recall** engine, vendored at `memory/` (FastAPI service; Postgres+pgvector, Neo4j, Redis)
- Tools: **MCP servers** in `tools/` (banks/AA, Tally, Zoho, GST/IMS, email, TReDS)
- Frontend: **Next.js 14** + TypeScript + Tailwind + shadcn/ui
- Queue/cache: Redis 7 (streams for agent jobs)
- Observability: Langfuse + OpenTelemetry GenAI conventions; append-only audit log
- Infra: Docker Compose (dev), GitHub Actions CI

## Architecture in one breath

Frontend → Backend API (auth, approvals, SSE) → Agent runs on Redis streams →
LangGraph state machine calls MCP tools and the Recall memory service →
deterministic **guardrails** validate every consequential action **outside the
LLM loop** → everything traced to Langfuse + audit log. Layer deep-dives in
`docs/architecture/`.

## Folder map

- `frontend/` Next.js app · `backend/` FastAPI app · `agents/` LangGraph graphs
- `tools/` MCP servers · `memory/` Recall (vendored — see its own CLAUDE.md)
- `shared/` generated contract models + shared types (never hand-edit generated code)
- `contracts/` **source of truth** for API/tool/memory/DB/event shapes
- `prompts/` all LLM prompts · `infra/` docker/CI · `docs/` architecture + team process

## Hard rules — violating these fails review

1. **Contract-first.** If your change alters any request/response/tool/event
   shape, update `contracts/` in the same PR and regenerate `shared/`. Never
   make the frontend guess.
2. **No money movement, no auto-send.** Anything that touches funds, sends
   external email, or files anything legal is *recommend-only* behind the
   approval gate. Guardrails are deterministic code in `backend/…/guardrails`
   and `agents/…/policies` — never prompt text.
3. **All prompts in `prompts/`**, loaded by name. No inline prompt strings.
4. **No raw SQL outside repository modules.** Engine/agent code stays ORM-free
   and provider-agnostic (protocols, not vendor SDKs).
5. **`memory/` is a vendored engine.** Tweak only: `memory/prompts/`,
   provider config, and FinDesk extension modules. Do not fork core math
   (decay/confidence/conflict) without an ADR.
6. **Tenancy everywhere.** Every query, memory call, tool call, and trace
   carries `tenant_id` (company) and acting `user_id`. No cross-tenant reads,
   ever.
7. **Schema changes via Alembic** migrations + `contracts/db.md` update.
8. **Tests:** pure logic → `*/tests/unit`; needs datastores → `*/tests/integration`
   (testcontainers, marked `integration`). CI runs unit on every PR.
9. **PII discipline:** no real financial data in fixtures, logs, or Langfuse
   traces (use the reference-pattern: IDs in traces, payloads in the store).

## Naming & conventions

- Python: ruff + mypy clean. TS: eslint + tsc clean. Components PascalCase,
  API routes snake_case, branches `feat/<short-name>`, conventional commits.
- IDs are UUIDv7 strings. Money is integer paise (`amount_paise`), never floats.
- Dates/times: timezone-aware UTC in storage; IST only at the presentation edge.

## Common commands

- `make up` full dev stack · `make dev` install all workspaces
- `make test` unit tests everywhere · `make test-int` integration
- `make lint` ruff+mypy+eslint · `make contracts` regenerate `shared/` from `contracts/`

## For multi-agent team work

Read `docs/team/agentic-coding.md`. Summary: stay inside the layer you own,
talk to other layers only through `contracts/`, never edit another layer's
internals to "make it work" — open an issue or change the contract with the
owner. Update this file (and your layer's CLAUDE.md) in the Friday sync; treat
it like production code.

## Memory & Context Protocol

Persistent memory lives in `knowledge/` (Obsidian vault, indexed by the
`basic-memory` MCP server registered in `.mcp.json`, project `findesk`) and in
the `graphify` knowledge graph (`graphify-out/`). The loop every session:

1. **Recall first.** Before exploring code, query what we already know:
   `graphify query "<question>"` for architecture/code questions, and the
   basic-memory MCP (`search_notes` / `build_context`) or
   `knowledge/00-INDEX.md` for decisions, conventions, and gotchas.
2. **context7 first for external libraries.** Any question about an external
   lib/API/version (Next.js, FastAPI, SQLAlchemy, framer-motion, …) goes to
   the context7 MCP before web search or guessing from memory.
3. **Write-through.** When you learn a durable fact (a decision, a broken
   path, a port remap, a contract shape), persist it immediately: update the
   right note under `knowledge/` (or `write_note` via MCP). Don't hoard it in
   the conversation.
4. **Close the session** with a dated log in `knowledge/sessions/` (template:
   `knowledge/templates/session-log.md`).

SessionStart/SessionEnd hooks in `.claude/settings.json` automate injection
and refresh (`scripts/memory/`). Never write secrets into the vault, scripts,
or any committed file — read keys from the environment at runtime.
