# 06 — Backend API Layer

**Owner:** Backend/API · **Code:** `backend/` · **Contracts:** `contracts/api.yaml`

FastAPI application: the only thing the frontend talks to, and the control
plane for everything the agents do. **No LLM call ever runs inside a request
handler** — the backend enqueues agent jobs and streams results.

## 1. Structure

```
backend/
  app/
    main.py            # app factory, middleware, routers
    auth/              # JWT sessions, RBAC, tenant switching (CA console)
    api/               # routers, one module per resource (thin)
    services/          # business logic (the only layer that touches db/)
    db/                # SQLAlchemy models, repositories, Alembic migrations
    guardrails/        # policy enforcement engine (see 05)
    approvals/         # approval workflow + token minting
    events/            # Redis stream producers, SSE bridge
    memoryclient/      # thin wrapper over Recall SDK (run-id stamping, budgets)
  tests/unit | tests/integration
```

Rules: routers stay thin (parse → service → respond). Services own
transactions. Repositories own SQL. Pydantic models at the edge are generated
from `contracts/api.yaml` into `shared/` — handlers import them, never
redeclare shapes.

## 2. API surface (summary — authoritative spec in `contracts/api.yaml`)

**Auth & tenancy** — `POST /auth/login`, `POST /auth/refresh`,
`GET /me`, `POST /tenants/{id}/switch` (CA multi-client)

**Books** — transactions, invoices/bills CRUD-lite + import endpoints,
`GET /books/exceptions` (unmatched residuals), `GET /reports/month-end`

**Agent control** — `POST /agent/runs` (kind + params) → `run_id`,
`GET /agent/runs/{id}`, `GET /agent/runs/{id}/stream` (SSE: step, tool,
status, done), `POST /agent/runs/{id}/cancel`

**Queues (the human side of the loop)**
- `GET/POST /conflicts` — conflict cards, one-tap resolution
- `GET/POST /anomalies` — anomaly cards, accept/dismiss/recover
- `GET/POST /approvals` — approval queue; decision endpoint mints the
  single-use `approval_token` and resumes the parked run

**Cash** — `GET /forecast` (versions, scenarios, lines),
`GET /receivables/radar` (45-day clocks, accrued interest),
`GET/POST /wc-actions` (ranked options, approve/reject)

**Explainability** — `GET /why/{entity_type}/{id}` — composed evidence chain
(app provenance + Recall why-chain), the A8 "Why?" button and B5 data room
share this.

**Webhooks/inbound** — AA consent callbacks, email events, TReDS status.

## 3. AuthN/AuthZ

- Short-lived JWT access + rotating refresh; argon2 hashing; optional TOTP.
- RBAC: `owner` (everything), `accountant` (books + queues), `ca`
  (multi-tenant read + queues per engagement), `viewer` (read-only).
- Every request resolves `(user_id, tenant_id, role)`; tenant comes from the
  token's active-tenant claim, switched explicitly — never from a query param.
- Approval decisions re-verify role *and* re-hash the action payload against
  the token request (no approve-then-mutate).

## 4. SSE streaming

Agent progress streams over `GET /agent/runs/{id}/stream` (SSE, not
websockets — simpler through proxies). Backend subscribes to `run:<id>` Redis
channels; events are the versioned shapes from `contracts/events.md`. The UI
renders live step/tool activity — agent legibility is a feature, not telemetry.

## 5. Approval engine

State machine per approval: `requested → pending → approved|rejected|expired`.
On `approved`: mint token (single-use, hash-bound, TTL), emit resume event.
On `rejected`: resume with rejection so the graph can re-plan or close out.
Escalation/expiry policies per action class. Every transition → audit log.

## 6. Performance posture

- Reads served from Postgres (+ small Redis caches); target p95 < 200ms for
  dashboard endpoints.
- Imports and anything LLM-flavored are jobs; the API returns `202 + run_id`.
- Pagination everywhere (`cursor` + `limit`), no unbounded lists.
