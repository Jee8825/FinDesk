# backend/ — API Layer Context

Read root `CLAUDE.md` first. Deep-dive: `docs/architecture/06-backend-api.md`,
schema in `contracts/db.md`, guardrails in `docs/architecture/05-guardrails.md`.

FastAPI + Pydantic v2 + SQLAlchemy 2 async + Alembic. The only thing the
frontend talks to; the control plane for agent runs and approvals.

## Rules for agents working here
1. Router → service → repository. Routers stay thin; services own
   transactions; ALL SQL in repositories; no LLM calls in request handlers
   (enqueue jobs, return `202 + run_id`).
2. `contracts/api.yaml` is the source of truth for the surface; `make
   contracts` generates path constants (shared/ts + frontend). Route Pydantic
   models mirror the contract **by review** — any shape change updates
   `contracts/api.yaml` in the same PR. (Schema codegen into `shared/py` is
   roadmap; see docs/product/crucible-layer-audit.md B4.)
3. Every query is tenant-scoped from the token claim — never from a query
   param. Money integer paise, UTC timestamps, UUIDv7 ids.
4. Schema change = Alembic migration (one per PR) + `contracts/db.md` update
   in the same PR. Books rows are never hard-deleted.
5. Guardrails are security-critical and live in `app/services/approvals.py`
   (maker–checker + inline tool execution), `app/services/statutory.py`
   (statutory clocks), and the tool layer's `approval_token` refusals:
   changes need ADR + dual review; tokens are single-use, action-hash-bound,
   and minted only at decision time.
6. `audit_log` is insert-only — never grant or use UPDATE/DELETE on it.
7. Tests: pure logic in `tests/unit`; anything touching Postgres/Redis in
   `tests/integration` (testcontainers, marked `integration`).
