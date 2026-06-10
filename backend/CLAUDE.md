# backend/ — API Layer Context

Read root `CLAUDE.md` first. Deep-dive: `docs/architecture/06-backend-api.md`,
schema in `contracts/db.md`, guardrails in `docs/architecture/05-guardrails.md`.

FastAPI + Pydantic v2 + SQLAlchemy 2 async + Alembic. The only thing the
frontend talks to; the control plane for agent runs and approvals.

## Rules for agents working here
1. Router → service → repository. Routers stay thin; services own
   transactions; ALL SQL in repositories; no LLM calls in request handlers
   (enqueue jobs, return `202 + run_id`).
2. Request/response models are generated from `contracts/api.yaml` into
   `shared/py` — import them, never redeclare shapes. Changing the surface
   starts in `contracts/api.yaml`.
3. Every query is tenant-scoped from the token claim — never from a query
   param. Money integer paise, UTC timestamps, UUIDv7 ids.
4. Schema change = Alembic migration (one per PR) + `contracts/db.md` update
   in the same PR. Books rows are never hard-deleted.
5. Guardrails (`app/guardrails/`) and approval tokens (`app/approvals/`) are
   security-critical: changes need ADR + dual review; tokens are single-use
   and action-hash-bound.
6. `audit_log` is insert-only — never grant or use UPDATE/DELETE on it.
7. Tests: pure logic in `tests/unit`; anything touching Postgres/Redis in
   `tests/integration` (testcontainers, marked `integration`).
