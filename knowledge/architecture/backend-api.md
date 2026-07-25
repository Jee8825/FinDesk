---
title: backend-api
type: note
permalink: findesk/architecture/backend-api
---

# Backend API (FastAPI, `backend/app`)

Contract: `contracts/api.yaml` → generated paths in
`frontend/src/lib/generated/api-paths.ts` (`API_PREFIX=/api/v1`) and
`shared/py`. Regenerate with `make contracts`.

## Route modules (`backend/app/api/`)
routes_books · routes_agent · routes_conflicts · routes_anomalies ·
routes_approvals · routes_radar · routes_forecast · routes_wc_actions ·
routes_dataroom · routes_reports · routes_why · routes_internal (worker ↔
backend, token-gated).

## Facts the UI depends on (verified in code)
- `/me` → `{email, active_tenant_id, role, memberships:[{tenant_id, tenant_name, role}]}`.
- `POST /tenants/{id}/switch` → full TokenPair (re-login as that tenant).
- Forecast scenarios keys: **`downside` / `base` / `upside`**
  (`agents/findesk_agents/graphs/cash_forecast/engine.py`).
- Approval `action_kind` values: **`commit_match`** (ledger),
  **`send_email`** (collections chaser), **`treds_listing`** (WC draft).
- Radar `escalation_level` ladder (`app/services/statutory.py`):
  `none → nudge → reminder → act_letter → samadhaan_prep`; clock = acceptance
  + 45d (MSMED Act); interest @ 3× bank rate.
- `/books/exceptions` returns the same `TxnPage` shape as `/books/transactions`.
- Auth: JWT bearer; login `founder@demo.findesk.in` / `demo1234` after seeding.

## Conventions
- Money integer paise; UUIDv7 ids; UTC ISO-8601; tenant scoping from the
  access token (never a query param).
- Settings in `app/config.py` (pydantic-settings, `env_file=".env"` — cwd
  sensitive, see [[system-overview]]).
- Audit log is append-only + hash-chained; `/why/{entity}/{id}` composes the
  evidence trail the [[frontend-ui]] Why? drawer renders.