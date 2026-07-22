---
title: 2026-07-15-improvement-sweep
type: note
permalink: findesk/sessions/2026-07-15-improvement-sweep
---

# Session — 2026-07-15 (evening) — Improvement sweep (10 items)

## Shipped
1. **Auth-refresh everywhere** — extracted `authorizedFetch` (single-flight
   401→refresh→retry) in `frontend/src/lib/api.ts`; uploads
   (`importStatement`, `onboardInvoices`) and the SSE hook
   (`useRunStream`) now go through it. Refresh round-trip verified via API.
2. **Anomaly "duplicate miss" was NOT a bug** — the WEWORK JUL pair was
   detected 2026-06-10, decided `recovered` (₹85,000), and dedupe_key rightly
   suppresses re-flagging. UX fixed instead: `api.anomalies()` now fetches
   all statuses; anomalies page shows "Recovered to date" strip (₹85k) so
   the headline KPI doesn't undersell after cleanup. Sidebar badge counts
   open-only.
3. **Forecast recompute on ledger commit** — new
   `backend/app/services/forecast_trigger.py` (debounced via
   `RunRepo.active_run`; enqueues *after* the run row commits — worker drops
   jobs whose run row isn't visible). Hooked in `/internal/recon/commit`
   (agent path) and approvals decide (human path). Verified: Sep statement
   upload → reconciliation → auto `cash_forecast` run
   (`params.trigger=ledger_commit`) → `generated_at` June 10 → now.
4. **Composed Why?** — `routes_why` now returns `memory: [MemoryBelief]`
   (scoped vendor/client beliefs + Recall provenance explanations via new
   `memoryclient.why_chain` / `ping`; parallel fetch, graceful when memory
   down). WhyDrawer renders a "what the agent believed" section. Verified:
   matched txn shows ledger.commit + 104-days-late belief + TDS belief.
5. **Real agent health** — contract-first `GET /agent/health` (api.yaml +
   regenerated shared/): worker = redis XINFO consumer idle < 30s (worker
   re-polls every 2s), memory = Recall /health ping. Sidebar badge now live
   (green pulse / red with "worker offline · memory offline" / neutral while
   loading). Verified both states by stopping recall.
6. **Quick wins** — Data Room share URL rendered inline (clipboard is
   best-effort); JWT_SECRET in `.env` was 16 bytes → now 48 (the pytest
   InsecureKeyLengthWarning came from this via cwd-relative .env);
   5 new unit tests (`test_why_compose.py`, `test_forecast_trigger.py`).
7. **Second tenant seeded** — `ensure_second_tenant` in seed script:
   "Meridian Textiles Co", same login, role `ca`, own chart. Verified
   `/tenants/{id}/switch` → active tenant + role ca. CA roster demoable.
8. **`scripts/dev_up.sh` / `dev_down.sh`** (+ `make dev-up` / `dev-down`) —
   idempotent one-command bring-up of the whole host-venv stack; logs+pids
   in `var/dev/`. Tested cold-restart of backend + full already-up pass.
9. **CI** — already comprehensive (ruff, workspace pytest, tsc+eslint+build,
   OpenAPI lint, generated-drift, secrets hygiene); nothing added.

## Gates
ruff clean · 70 unit tests pass (was 65) · tsc 0 · eslint 0 ·
`npm run build` ✓ (21/21 pages) · contracts regenerated, no drift.

## Notes / residual
- Browser-pane MCP was down this session → UI changes verified by build +
  API behavior; do a quick visual pass next session (badge, drawer memory
  section, share URL input, roster switch).
- JWT secret rotation invalidates existing sessions (expected; re-login).
- Frontend still has no JS unit-test runner — Playwright smoke remains open.
- Anthropic key in `memory/.env` still needs rotation by a human.
