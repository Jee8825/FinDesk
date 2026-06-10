# 04 — Data & Storage Layer

**Owner:** DB & Storage · **Code:** `backend/app/db`, `infra/` · **Contracts:** `contracts/db.md`

Four stores, four jobs. The app DB is the **system of record for facts**;
Recall's stores hold **beliefs**; Redis moves **work**; Neo4j (inside the
memory service) holds **evidence**.

## 1. App database (Postgres 16)

Owned by the backend; accessed by agents only through backend services.
SQLAlchemy 2 async + Alembic. Every table carries `tenant_id` and row-level
security is enabled in prod.

### Core schema (summary — authoritative DDL in `contracts/db.md`)

**Identity & tenancy**
- `tenants` — company, GSTIN(s), MSME registration (Udyam), plan, entity tree
  (multi-entity under Growth plan)
- `users`, `memberships` — RBAC roles: `owner`, `accountant`, `ca`, `viewer`;
  a CA user holds memberships across many tenants (multi-client console)
- `counterparties` — unified vendor/client master: contacts, GSTIN, MSME
  status (drives 45-day obligations *both ways*), TDS section defaults

**Books (Module A)**
- `bank_accounts`, `bank_transactions` — normalized statement lines, source
  provenance, hash-deduped
- `invoices` (AR), `bills` (AP), `expenses` — with GST/TDS breakdowns,
  e-invoice IRN where present
- `matches` — txn ↔ document links: type (`full|partial|fee|tds_adjusted`),
  confidence, matched-by (`agent|human`), critic verdict
- `ledger_entries` — committed double-entry rows; chart of accounts per tenant
- `conflicts` — open/resolved conflict cards: both claims, confidences,
  hypotheses, resolution, resolver, memory backref
- `anomalies` — typed cards (`duplicate|overcharge|out_of_pattern`), evidence
  refs, recommended action, recoverable-money flag, status

**Cash (Module B)**
- `payment_observations` — per-invoice promised vs actual, nudge→pay latencies
  (feeds B1 via memory)
- `statutory_clocks` — per-receivable/payable 45-day state machine: acceptance
  date, day count, accrued interest (compound, per MSME Act), escalation level
- `forecasts`, `forecast_lines` — versioned 4/13-week scenario runs (base/
  upside/downside) with per-line traceability to invoices/behaviors
- `wc_actions` — ranked working-capital options: kind (`treds|collect|retime`),
  cost, unlock amount, status (`proposed|approved|executed|rejected`)

**Control plane**
- `approvals` — the approval queue: action payload, requested-by run/step,
  policy verdicts, decision, decider, decided_at; **approval_token** issuance
- `agent_runs`, `agent_steps` — run registry + LangGraph checkpoints
- `audit_log` — append-only (insert-only role), hash-chained rows; powers
  Why-chains together with provenance
- `documents` — uploaded files in object storage (S3-compatible), metadata +
  content hash here, bytes never in Postgres

### Conventions

- PKs UUIDv7; money `BIGINT` paise; `created_at/updated_at` UTC; soft deletes
  only where a regulator would expect history (books are never hard-deleted).
- Migrations: Alembic, one revision per PR max, reversible where possible.
  Schema change ⇒ same-PR update to `contracts/db.md`.

## 2. Redis 7

- **Streams** `agents:interactive`, `agents:batch` — job transport (see 01).
- **Pub/sub→SSE bridge** — `run:<id>` channels feed backend SSE to the UI.
- Short-lived caches: dashboard aggregates, GSTR-2B pulls, idempotency keys.
- Nothing durable lives only in Redis.

## 3. Memory-service stores (owned by `memory/`, see 03)

Postgres+pgvector (units, embeddings), Neo4j (provenance), Redis (working
memory/prefetch). **App code never connects to these directly** — HTTP API
only. Backup/restore handled per-service.

## 4. Object storage

Statements, invoices PDFs, generated reports, MSME Samadhaan draft documents
— S3-compatible bucket per environment, tenant-prefixed keys, server-side
encryption, lifecycle rules (originals retained ≥ 8 years per Indian books
retention norms).

## 5. Data classification & retention

| Class | Examples | Handling |
|---|---|---|
| Financial-sensitive | transactions, invoices, balances | encrypted at rest, RLS, never in traces |
| Credentials/consents | AA consent artefacts, OAuth tokens | secret manager, never in DB plaintext |
| Derived beliefs | memory units, baselines | deletable per tenant atomically (Recall supports it) |
| Telemetry | spans, metrics | reference-pattern only (IDs, no payloads) |

Tenant offboarding = app-DB tenant purge + Recall atomic deletion + object
storage prefix delete + provenance cascade, executed by one audited script in
`scripts/`.
