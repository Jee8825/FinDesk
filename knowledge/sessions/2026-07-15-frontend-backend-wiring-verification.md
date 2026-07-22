---
title: 2026-07-15-frontend-backend-wiring-verification
type: note
permalink: findesk/sessions/2026-07-15-frontend-backend-wiring-verification
---

# Session — 2026-07-15 — Full-stack wiring verification + DataRoom NaN fix

## What happened
- Brought the whole stack up from cold: Docker Desktop → app-postgres (15433)
  + app-redis (6380) → uvicorn from repo root (8080) → agents worker →
  frontend (3001). All per [[system-overview]] runtime notes — no surprises.
- **API surface audited**: every `api.*` method the 18 pages call exists in
  `src/lib/api.ts`; all 16 backend GET/POST endpoints return 200 with real
  demo data (paths are hyphenated: `/books/chart-of-accounts`, `/wc-actions`,
  `/reports/month-end`).
- **Browser-tested every page** (dashboard, transactions, reconciliation,
  categorization, conflicts, anomalies, approvals, radar, collections,
  forecast, wc-actions, reports+why, dataroom, share, onboarding, settings,
  ca). Zero console errors, zero server errors.
- **Interactions exercised end-to-end**: conflict resolve (POST 200 + badge
  2→1), approval approve (badge 3→2), anomaly scan run, collections draft run
  (produced 2 new approvals, badge →4), Why? drawer, share-token mint +
  unauthenticated lender view, statement upload through the Next proxy →
  full LangGraph run streamed over SSE (fetch→parse→ingest→match→categorize→
  critic→commit→learn→succeeded), re-import deduped (25 txns before/after).
- **Bug found & fixed**: DataRoom "Debits categorized" rendered **NaN** —
  backend sends `evidence.debits_categorized` as a *string* `"13/13"` but
  `DataRoomView.tsx` forced all evidence values through `Number()`. Fixed by
  branching on `typeof value === "number"` (contract leaves evidence loose;
  the TS type already allowed `string | number | null`). Verified in browser.
- **All checks green**: tsc 0 errors, eslint 0 warnings, ruff clean,
  65 backend+agents unit tests passed, 30 memory unit tests passed.

## Durable facts learned
- Forecast band "parallelograms" are correct: scenarios shift one large
  inflow to weeks 3/6/8 (upside/base/downside) and converge at horizon end.
- `evidence.debits_categorized` in the dataroom payload is a string
  ("13/13") — any renderer must not coerce evidence values to Number.
- Statement re-import is idempotent (dedupe on ingest) — safe to re-upload.

## Open threads / next session should
- **Recall memory service is not running** — worker logs
  "memory recall skipped (All connection attempts failed)" on every run and
  degrades gracefully. Bringing it up needs pgvector+Neo4j+Redis (memory
  compose still broken per [[2026-07-14-ui-rebuild-and-memory-layer]]).
- Share-link UX: token is clipboard-only ("Link copied ✓" for 4s); if
  `navigator.clipboard` is unavailable the user never sees the link —
  consider showing the URL inline as fallback.
- `make up` remains broken (documented local-venv-only workflow).
