---
title: 2026-07-23-crucible-next-round
type: note
permalink: findesk/sessions/2026-07-23-crucible-next-round
---

# Session — 2026-07-23 — Next-round crucible: landscape re-scan + feature roadmap

Ran project-crucible (STRESS-TEST + DISCOVER) on the post-hardening repo.
Full report: `docs/product/crucible-next-round.md`.

## Landscape facts (July 2026)
- GST **IMS mandatory since 1 Apr 2026** — statutory ITC gate (Sec 38
  substituted Oct 2025). Accept/reject/pending now determines ITC.
- GSTR-3B **hard-locked** since Jul-2025 period; fixes only via GSTR-1/1A.
- **TallyPrime 7.0/7.1**: IMS surfacing, connected banking (Axis/SBI/ICICI),
  **TallyIra AI** (Jun 2026) — incumbent entered Module A's lane.
- AA/FIU gate unchanged (no FIU-Lite). DPDP rules notified 13 Nov 2025;
  hard enforcement ~May 2027.

## Verdict
Differentiate up-stack: gate + provenance + statutory math + forecast
fusion. Never race TallyIra at data entry.

## Roadmap (impact ÷ effort)
1. Claims pass (observability + AI language) — hours
2. **F1 IMS Copilot** fixture-first (`ims@v1` reserved; set_state ⚠) — 1–2 wk
3. **F2 month_end_close graph** (composition over existing endpoints) — 1–2 wk
4. F3 collections outcome loop — closes seed-only memory gap — 3–5 d
5. F4 Udyam Vendor Verify (msme_status is self-declared today) — 3–5 d
6. F5 glass-box run viewer (persist emitter.step events) — 3–5 d
7. W1 live-Tally banked proof — 1 d · W2 DPDP note — 1–2 d · F6 CA rollup — 1 wk

## Gaps found in current shape
- Collections graph has **no memory write-back** (behavior loop = seed-only).
- `Counterparty.msme_status` nullable self-declared string — shield scoping
  depends on it; commodity Udyam APIs exist (IDfy/AuthBridge/Deepvue).
- Docs claim Langfuse+OTel; **zero wiring** in code.
- `prompts/` has exactly one prompt; only recon imports llm.py.

## Kill log (closed directions)
Bharat Connect (BD-gated), einvoice cross-check (commodity), Zoho-now,
GSTR filing product (liability), UPI-links-as-feature, AA-now, NL→SQL chat,
WhatsApp channel, payroll module.

## Part 2 — Frontend & Backend layer audit (same day)

Report: `docs/product/crucible-layer-audit.md`. Backend: no Criticals.
Key fixes: FE1 forecast 6s-timer invalidate → stream run.done; FE2
useRunStream no-reconnect + done-on-error; FE3 cursor never sent (50-row
dead-end); B1 auth pack (no rate limit, stateless refresh) + FE4 cookie
migration = pre-pilot gate; B4 contract codegen CI (shapes hand-mirrored
both sides today). Layer CLAUDE.mds drifted from reality (5 claims listed
in report). SSE server path is production-grade — keep. Add-on build lists
for F1–F6 are in the report, per layer, with effort.

## Part 3 — Autonomous build session (same day): all phases shipped

13 phases, 12 commits on feat/crucible-hardening. Everything live-verified
against the running stack, gates green at close:
**161 py-unit (69 backend / 60 agents / 32 tools) · 33/33 Playwright
(incl. 3 IMS + 6 axe-a11y) · ruff clean · tsc/eslint clean · prod build ✓
· migrations through 0016 · contracts regen no-drift (48 ops).**

Shipped: FE1/FE2 stream correctness (useGraphRun replaces 3 timer
invalidates; reconnect+poll-fallback hook) · layer CLAUDE.md honesty ·
**F1 IMS Copilot** end-to-end (ims tool + 0014 + classify tiers + gated
set_state in decide_approval + /ims triage page; live: PB-889 accept →
receipt with token) · **F5 Run Viewer** (/runs + /runs/[id], durations,
critic-gate chip; live: 5-step forecast run, 43ms) · FE3 infinite cursor
+ FE7 ApiError · **F3 outcome loop** (payment_promises 0015, late_phrase
shared twin, recon settle hook writes lateness+PTP outcomes to Recall,
radar PTP capture; live-verified) · **F4 Udyam verify** (udyam tool +
0016 + effective_mse verified-beats-tag; live: Kaveri small→medium drift
excluded bill + alert) · **F2 close checklist** (8 evidence checks,
blockers/warnings, audited signoff, close pack via shared
build_export_payload; live: honestly blocked on 19 unmatched) ·
**B1/B2/B3** (login 5/min + refresh rotation w/ jti denylist + logout —
live: 429 on 6th, replay 401; /readyz; X-Request-ID) · polish (formatIST
everywhere, terrain code-split, axe-enforced WCAG on 6 surfaces).

Deliberately NOT done: F6 CA rollup (cross-tenant read vs hard rule 6 —
needs a human decision on membership-scoped aggregation); FE4 cookie
migration (deferred pre-pilot, documented); month_end_close as agent
GRAPH (composition service delivers the value; graph wrapper is a later
lap); heavy skill-audit passes at session end (context spent on
shipping+verifying; axe CI check embodies the a11y audit permanently).

Gotchas added: e2e specs must wait-for-data before branching on
row-count; code-split chunks need expect.poll on canvas size; the
limiter counts successful logins too (clear auth:rl:* between manual
tests); receipts land relative to backend cwd (backend/var/...).

## Part 4 — "do next what needed": PR + guard + close graph + DPDP

- Pushed 12 commits; opened PR #18 (base main).
- **B4 shipped**: scripts/check_api_surface.py — mounted /api/v1 routes ⇄
  api.yaml, both directions, in CI (test-python) + make contracts. First
  run caught 3 phantoms (runs/cancel, both webhooks) → demoted to roadmap
  comments; registry now 45 real ops.
- **month_end_close graph shipped** (catalog's last planned entry):
  fetch_checklist → critic (reducer cross-check, 7 pure tests) → persist
  (close.checklist_run audit; NEVER sign-off — human act stays on public
  API). Internal /close/context + /close/run; palette + CloseCard "Run
  close agent". Live: succeeded 32ms, blockers=2, ready=false honest.
- **W2**: docs/product/dpdp-posture.md — clock, data inventory, built
  posture, pre-pilot gap list (erasure vs never-hard-delete tension noted).
- Ops gotchas: `next build` while dev server runs corrupts .next
  (vendor-chunks error) → rm -rf .next + restart; Recall API (:18000) +
  embedding shim (:8090) are host processes that die with the terminal —
  smoke's agent-health spec fails until restarted (dev_up.sh has the
  exact invocations).
- Still open for a human: F6 CA rollup design; FE4 cookie migration;
  live-Tally banked proof (needs a running TallyPrime).
