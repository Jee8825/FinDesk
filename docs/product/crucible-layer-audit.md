# FinDesk — Frontend & Backend Layer Audit

**Mode:** STRESS-TEST (engineering, per-layer) · **Date:** 2026-07-23
**Reviewed:** `main.py`, auth stack (`routes.py`, `security.py`, `deps.py`), `config.py`, `routes_books.py`, `routes_agent.py` (SSE full path), `routes_internal.py` token check, `books_repo.py`, `models.py` indexes; frontend `api.ts` (full), `useRunStream.ts` (full), `providers.tsx`, `next.config`, `globals.css`, forecast/onboarding/ca pages, `package.json`, e2e specs; both layer CLAUDE.mds. Evidence for this round is the code itself — every claim carries a `file:line`.
**Companion:** product-level roadmap in `crucible-next-round.md` (F1–F6 referenced below).

---

## What the layers get right

Worth naming precisely, because these are the parts to build on, not rework:

**Backend** — argon2 password hashing, typed access/refresh JWTs with 15-min access TTL ([security.py](backend/app/auth/security.py)); fail-fast boot refusing non-dev with dev secrets ([config.py:53](backend/app/config.py)); structured 500s with a log-correlated `ref` ([main.py:52](backend/app/main.py)); upload guards — size cap, empty check, sha256, per-tenant dir ([routes_books.py:66](backend/app/api/routes_books.py)); cursor pagination clamped at 500 in the repo ([books_repo.py:79](backend/app/db/books_repo.py)); tenancy exclusively from the token claim ([deps.py](backend/app/auth/deps.py)); constant-time internal-token compare ([routes_internal.py:30](backend/app/api/routes_internal.py)); real worker liveness from consumer idle ([routes_agent.py:60](backend/app/api/routes_agent.py)); and an SSE stream that is genuinely production-grade — subscribe-first-then-replay with dedup, 15-s keepalives, terminal-state replay ([routes_agent.py:130–180](backend/app/api/routes_agent.py)). `[V]` all.

**Frontend** — single-flight token refresh shared across concurrent 401s ([api.ts:40](frontend/src/lib/api.ts)); same-origin `/api/v1` rewrite so no CORS surface exists ([next.config.mjs](frontend/next.config.mjs)); generated API paths; sane react-query defaults (staleTime 5s, retry 1); `prefers-reduced-motion` honored globally *and* per-component ([globals.css:283](frontend/src/app/globals.css), fx.tsx, ForecastTerrain); global `:focus-visible`; paise-in formatINR with lakh/crore compact notation; a cmdk command palette with its own e2e spec. `[V]` all.

## Layer CLAUDE.md vs. reality

The recurring crucible lesson — docs drift — has moved down a level. Root README/CLAUDE were fixed in lap 1; the *layer* files were not:

| Claim | Reality | |
|---|---|---|
| backend rule 5: guardrails in `app/guardrails/`, tokens in `app/approvals/` | Neither directory exists; logic lives in `services/approvals.py` + tool refusals | `[V]` `ls` this run |
| backend rule 2: request/response models "generated from `contracts/api.yaml` into `shared/py` — import them, never redeclare" | Every route file declares its own Pydantic models (auth/routes.py:17, routes_agent.py:40, routes_books.py:266…) | `[V]` |
| frontend rule 1: "API access ONLY through the generated client in `shared/ts`" | Paths are generated (`lib/generated/api-paths.ts`); ~350 lines of response **types** are handwritten in [api.ts](frontend/src/lib/api.ts) | `[V]` |
| frontend rule 3: "Server Components for reads" | 22 of 24 app-router files are `"use client"`; zero server-component reads | `[V]` |
| frontend rule 2: "Feature folders under `src/features/<area>`" | No `src/features/` exists | `[V]` |

The pragmatic choices are defensible — the *claims* are not. Either normalize the docs to reality (an hour) or do the codegen the docs promise (see B4, which makes the drift class impossible instead of fixing instances).

---

## Backend findings

**Critical — none.** Nothing in the backend will fail in the demo context. Say it plainly: this layer is in good shape.

### Important

**B1. Auth hardening pack (the pre-pilot gate).**
- **What:** No rate limiting anywhere (`grep slowapi|limiter|RateLimit` → empty `[V]`) — `/auth/login` accepts unlimited attempts. Refresh tokens are stateless with no rotation, no `jti`, no server-side revocation ([routes.py:71](backend/app/auth/routes.py)) — logout is purely client-side (`clearTokens`), so a stolen refresh token works for 14 days and nothing can kill it. Tenant switch mints a new pair but old-tenant tokens stay valid to expiry.
- **Why it matters:** fine for fixture data; disqualifying the day a real SME's books are behind it. Judges who probe security will find login brute-force in minutes.
- **Fix:** Redis token-bucket on login/refresh (in-house, ~50 lines, no new dep); refresh rotation with `jti` + Redis denylist; `/auth/logout` that revokes. **1–2 days.**

**B2. Readiness is fictional.** `/healthz` returns static ok ([main.py:66](backend/app/main.py)) — a deploy goes green with Postgres down. Add `/readyz`: `SELECT 1` + Redis ping (+ optional Recall ping, non-fatal). **Hours.**

**B3. No request correlation on the happy path.** The error handler mints a `ref` only on 500s; successful requests carry no `X-Request-ID`, so frontend↔backend↔worker debugging has nothing to join on. Middleware that stamps/propagates one (and logs it) — **hours**, and it's the precondition for F5's run-trace story crossing layers.

**B4. Contract sync is manual on both sides.** Shapes live in `contracts/api.yaml`, then get hand-mirrored into route Pydantic models *and* into api.ts types — two copies that drift silently (this is the same failure class as lap 3's duplicated audit walker). **Fix at the class level:** CI job that generates OpenAPI from the FastAPI app and diffs it against `contracts/api.yaml`, plus `openapi-typescript` to emit the api.ts types from the same file. **1–2 days**, kills the whole category, makes the CLAUDE.md claims true instead of false.

### Worthwhile

- **B5.** Unbounded reads that are fine now, walls later: `unmatched_transactions` has no limit ([books_repo.py:82](backend/app/db/books_repo.py)); list endpoints (approvals, anomalies, conflicts) return full scans. Cap + cursor before pilot data volumes.
- **B6.** Hot listing queries run on single-column indexes; add composite `(tenant_id, id desc)` and `(tenant_id, match_status)` when row counts justify a migration. Cheap, not urgent. `[V]` models.py shows per-column only.
- **B7.** `login` picks `memberships[0]` as active tenant ([routes.py:63](backend/app/auth/routes.py)) with no explicit ordering — a multi-tenant CA's landing tenant can flip between logins. Order deterministically or persist last-active. Small.
- **B8.** SSE resume: the server already replays persisted steps on connect — honoring `Last-Event-ID` (or `?since=`) would let a reconnecting client skip the re-replay. Pairs with FE2.

### Optional
Security-header middleware (matters only when the API is served without the Next rewrite in front); MIME allowlist on uploads (the parser rejects garbage anyway); OTel spans once the observability claim returns (F5).

---

## Frontend findings

### Important

**FE1. Forecast refresh fires and hopes.** `onSuccess: setTimeout(() => invalidateQueries(["forecast"]), 6000)` ([forecast/page.tsx:298](frontend/src/app/(app)/forecast/page.tsx)) — the run's duration is unknown; if it takes 7s the page refetches the *old* forecast and presents it as the result of the refresh, with no progress shown meanwhile. The correct pattern already exists in the codebase (onboarding uses `useRunStream`): start run → stream → invalidate on `run.done@v1`. **~half day**, and it generalizes to every run-triggering surface.

**FE2. A dropped stream looks like a finished run.** `useRunStream` has no reconnect; any network blip lands in `catch` → appends `stream.error` → `finally { setDone(true) }` ([useRunStream.ts:56–62](frontend/src/hooks/useRunStream.ts)). Mid-run disconnect = UI says done while the worker is still working. Fix: retry with backoff (the server replays persisted steps on reconnect, so state self-heals); set `done` only on a real `run.done@v1` or explicit failure. **~1 day.** With FE1 this is the difference between a demo that survives conference Wi-Fi and one that doesn't.

**FE3. Pagination dead-ends at 50 rows.** The server implements cursors; the client never sends one — `api.transactions()` takes only a status filter ([api.ts:459](frontend/src/lib/api.ts)), and no page passes `cursor`. The books page shows counts from `transaction_counts` next to a list that silently truncates: a judge importing a real statement sees "1,240 transactions" and 50 rows with no way to reach the rest. **~half day** (load-more with `next_cursor`, or infinite query).

**FE4. Token storage + route gating (pre-pilot posture, pairs with B1).** JWTs in `localStorage` ([api.ts:5](frontend/src/lib/api.ts)) are readable by any XSS; there is no `middleware.ts`, so unauthenticated visits render full page shells before the 401 bounce. The same-origin rewrite makes the strong pattern cheap: httpOnly-cookie sessions + Next middleware gate, no CORS work needed. **1–2 days coordinated with B1.** Acceptable for the hackathon; a blocker for real books.

### Worthwhile

- **FE5.** "IST at the edge" is honored once: brief/page.tsx passes `Asia/Kolkata`; every other date renders with `en-IN` *locale* — which uses the **browser's** timezone `[V]` (page.tsx:125, approvals:58, WhyDrawer:120). Correct in an India demo room, wrong the day anyone opens it abroad. One `formatIST()` util + sweep. **Hours.**
- **FE6.** `ForecastTerrain` (three + fiber + drei + paper-shaders — the heaviest dependency cluster in package.json) is statically imported on the forecast page ([page.tsx:19](frontend/src/app/(app)/forecast/page.tsx)). `next/dynamic({ssr:false})` with the already-existing `BandsChart` fallback as loading state splits ~0.5 MB from the money page's first paint. **Hours.** (Check `next build` output first — if Next already split it, this collapses to a note.)
- **FE7.** `request()` throws `Error(detail)` — the HTTP status is discarded ([api.ts:88](frontend/src/lib/api.ts)), so pages can't distinguish 403 (show "ask your admin") from 422 from 500. A small `ApiError {status, detail}` class. **Hours.**
- **FE8.** The WCAG 2.1 AA claim on signature surfaces is untested — 27 aria/role usages, good focus-visible and reduced-motion foundations, zero automated checks. `@axe-core/playwright` assertions on the five signature surfaces make the claim CI-enforced. **~1 day.**

### Optional
Print stylesheet for reports/dataroom (lenders print); share-token travels as a query param (acceptable for expiring read-only links — document the choice); skeleton-vs-spinner consistency pass.

---

## Add-on build lists (mapped to F1–F6 in crucible-next-round.md)

### Backend add-ons

| For | Build | Notes |
|---|---|---|
| **F1 IMS** | `tools/findesk_tools/ims/` fixture server (contract `ims@v1` already reserved, `set_state` ⚠) · `services/ims_match.py` deterministic tiers (GSTIN+doc+amount exact → tolerance → unmatched) · `GET /ims/queue`, `POST /ims/{id}/action` → approval request, never direct · `itc_at_risk_paise` into payables totals + a tagged forecast driver | Mirrors the tally-connector pattern exactly; recon owns matching idioms |
| **F2 Close** | `services/close.py` checklist aggregation over existing services · `GET /close/checklist`, `POST /close/signoff` (maker-checker) · close pack = extend `dataroom_export` zip | Composition only; no new engines |
| **F3 Outcome loop** | PTP columns on Invoice or a `promises` table (Alembic) · `POST /collections/promise` · settlement hook in recon calls `remember()` with observed lateness + promise-kept | The forecast's recall path consumes it unchanged |
| **F4 Vendor verify** | `tools/findesk_tools/udyam/` fixture verify · `msme_verified_status`, `msme_verified_at` on Counterparty · FY-boundary drift check surfacing in payables `ca_note` | Never overwrite the human-tagged field; show both |
| **F5 Trace** | Steps are already persisted with the run — add durations to `StepOut` and an optional `GET /agent/runs/{id}/trace` with tool/memory call annotations from audit | B3's request-id makes traces joinable |
| Platform | B1 auth pack · B2 `/readyz` · B3 request-id · B4 contract codegen CI | The pre-pilot gate |

### Frontend add-ons

| For | Build | Notes |
|---|---|---|
| **F5 Run Viewer** | `/runs/[id]` glass-box page: timeline from persisted steps + live SSE tail, per-node durations, critic verdict chip, memory-hit markers, jump-to-approval | Highest demo value per line of code in the repo; data already exists |
| **F1 IMS queue** | Triage table (accept/reject/pending) with evidence drawer (matched bill, Tally source, bank trail), ITC-at-risk hero tile, bulk-action → approvals handoff | Reuse anomaly-row + approval patterns |
| **F2 Close page** | Checklist with per-line evidence links (Why? drawer refs), sign-off flow, pack download | The demo's closing scene |
| **F3 PTP** | Capture modal on collections queue rows; kept/broken badge on radar items | |
| **F4 badges** | verified-MSME badge + "status changed at FY boundary" alert strip on payables | |
| **F6 CA strip** | Cross-tenant "needs action today" rollup on `/ca` | Optional by pitch date |
| Fixes | FE1–FE4 above | FE1+FE2 first — they make every other demo trustworthy |

## Roadmap (Monday order, both layers)

1. **FE1 + FE2** — stream correctness; every subsequent demo depends on runs looking truthful — **1–2 d**
2. **Layer CLAUDE.md normalization** (+ start B4 CI diff) — **half day**
3. **F1 backend** (ims fixture + match + endpoints) — **3–4 d** → **F1 frontend** queue — **2–3 d**
4. **Run Viewer** — **2–3 d** (parallelizable with F1 frontend)
5. **FE3 pagination + FE7 error taxonomy** — **1 d**
6. **B1 + FE4** auth/cookie pack — **2 d** — the pre-pilot gate, schedule before any real-data pilot
7. **B2 + B3** readyz + request-id — **half day**
8. **FE5 + FE6 + FE8** polish — **1–2 d**

## What would make me wrong

- If `next build` already code-splits the terrain chunk, FE6 drops to a note — check the build output first.
- If an auth gate exists somewhere non-standard (custom layout redirect logic I didn't trace), FE4's "shells render first" half weakens; the localStorage half stands regardless.
- If `routes_internal`'s inline models are deliberately exempt from the contract rule (worker-internal surface), B4's scope narrows to the public API — the fix is then to say so in backend/CLAUDE.md rule 2.
- I did not run the app or measure bundles this session — perf claims are code-read inferences `[I]`, not profiles. A `next build` + Lighthouse pass would firm them up in 20 minutes.

## Honest verdict

Both layers are unusually sound for their stage — argon2, clamped cursors, subscribe-first SSE with keepalives, single-flight refresh, reduced-motion discipline: these are choices teams usually get wrong. The real gaps cluster in two places. First, **truthfulness under failure in the frontend**: a timer-based refetch and a no-reconnect stream mean the UI can present stale or half-finished agent work as done — for a product whose entire identity is "trust the agent's evidence," FE1/FE2 are the highest-leverage fixes in either layer. Second, **the pre-pilot security pack** (B1/FE4): correct to defer during fixtures, mandatory before real books. The add-on lists are deliberately shaped so F1's backend reuses the tally/recon patterns and F5's viewer is mostly UI over data you already persist — the architecture keeps paying for itself.
