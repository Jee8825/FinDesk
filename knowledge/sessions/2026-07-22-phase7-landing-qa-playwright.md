---
title: 2026-07-22-phase7-landing-qa-playwright
type: note
permalink: findesk/sessions/2026-07-22-phase7-landing-qa-playwright
---

# Session — 2026-07-22 — Phase 7 landed + visual QA + Playwright smoke

## Shipped
1. **PR #16** (`feat/phase7-improvement-sweep` → `dev`) — landed the four
   uncommitted sessions (UI rebuild, memory layer, wiring, improvement
   sweep): 90 files, ~6.4k insertions. Gates before commit: ruff clean ·
   113 unit tests (backend 26, agents 44, tools 13, memory 30) · eslint 0 ·
   tsc 0 · contracts regen no drift. `.gitignore` hardened: `.obsidian/`,
   `.claude/settings.local.json`, `*.tsbuildinfo`, playwright artifacts.
2. **Visual QA pass** (the one deferred from 07-15 — browser pane was down
   then). All five verified against the live dev stack, screenshots in
   conversation:
   - sidebar **agent-health badge** → "agent · all systems live"
   - **WhyDrawer memory section** → "what the agent believed" with both
     beliefs (104-days-late @ conf 0.90, 5% TDS @ 0.35) + evidence chains +
     ledger.commit provenance, on the matched BLUE TOKAI txn
   - **anomalies recovered strip** → ₹85,000 · "2 findings caught & decided"
   - **Data Room share URL inline** → readonly input with signed JWT;
     lender view opens read-only, expiry 7d, audit chain ticked 76→77
     events (the share itself audited)
   - **CA roster tenant switch** → Demo ↔ Meridian both directions,
     POST /tenants/:id/switch 200, sidebar card + scoping update
3. **Playwright smoke suite** — frontend's first JS test runner.
   `frontend/e2e/` (auth.setup.ts logs in via UI → storageState;
   smoke.spec.ts: 8 page renders, health badge live, recovered strip,
   inline share link, roster tenants). `npm run test:e2e` /
   `make test-e2e`. **13/13 in ~10s** against the dev_up stack.
4. Anthropic key in `memory/.env` rotated (human-done, was flagged 07-15).
5. **contracts/api.yaml made valid OpenAPI** — CI's OpenAPI lint is
   path-filtered, and this PR's `/agent/health` contract change re-ran it
   for the first time since Phase 5, surfacing two latent errors: the
   `/receivables/radar` summary was an unquoted flow scalar (commas split
   "accrued interest"/"escalation states" into invalid operation keys), and
   none of the 10 parameterized paths declared their `parameters`. Both
   fixed; `openapi-spec-validator` green; shared/ regenerated (digest bump
   only).

## Gotchas (durable)
- **npm cache strips large binaries** on this machine:
  `@next/swc-darwin-arm64` in the npm cache had README+package.json but no
  `.node` binary → `npm install`/`--force` keep restoring the gutted copy →
  `next dev` dies with "Failed to load SWC binary". Fix: `npm pack
  @next/swc-darwin-arm64@<ver>` (registry tarball has the binary), then
  `tar -xzf … --strip-components=1 package/next-swc.darwin-arm64.node`
  into `node_modules/@next/swc-darwin-arm64/`.
- **Browser-pane MCP drops pointer events while the pane is hidden**
  (clicks/scrolls silently no-op or time out; screenshots + read_page +
  form_input keep working). Verify clicks landed via
  `read_network_requests`; fall back to ref-clicks after fronting, or
  assert handlers via DOM click as a diagnostic.
- Playwright specs: the Data Room share URL is an `<input value=…>` —
  `getByText` can't match input values, use
  `locator('input[value*="/share?token="]')`.
- **Path-filtered CI hides latent failures**: jobs gated on `changes`
  (contracts, etc.) can stay green for phases while their input is broken —
  the first PR to touch that path inherits the blame. When a filtered job
  fails, check `git log` on the offending lines before assuming the PR
  introduced it (and pre-run `pipx run openapi-spec-validator
  contracts/api.yaml` whenever touching contracts).

## Residual
- CI does not run the e2e suite (needs full stack; deliberate). Candidate:
  nightly job with dockerized stack.
- `make lint`/`make test` still swallow failures with `|| true` — run raw
  commands when you need real exit codes.
- PR #16 awaits review/merge into `dev`.
