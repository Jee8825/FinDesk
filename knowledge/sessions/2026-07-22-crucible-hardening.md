---
title: 2026-07-22-crucible-hardening
type: note
permalink: findesk/sessions/2026-07-22-crucible-hardening
---

# Session — 2026-07-22 (night) — Crucible stress-test + autonomous hardening run

Two-part session. First: installed the personal `project-crucible` skill and
ran a STRESS-TEST on FinDesk itself (report:
`docs/product/crucible-stress-test.md`) — evidence-driven red-team with web
research on the Indian market/regulatory landscape. Then: user-approved
autonomous 8-question round → full phased run on branch
`feat/crucible-hardening` (off feat/design-v2), one commit per phase, pushed
per phase.

## Crucible findings that drove the work
- **C1** — docs claimed 9 tool servers; 4 existed, all file/sandbox. The Tally
  connector *is* the product for Indian SMEs (CredFlow/Suvit built moats on
  Tally sync).
- **C2** — "banks/AA" implies FIU status; RBI rule: FIU must be a regulated
  entity — pure SaaS path is TSP + FIU partner. Statement-first is the honest
  MVP.
- **I1** — 43B(h) backlash (40k+ MSME de-registrations, CMAI ₹5-7k cr order
  losses reported) inverts the enforcer assumption: suppliers fear
  escalation. Buyers have the legal compulsion (deduction deferral).
- **I2** — CredFlow ≈ Module B's chase+predict (N1 there); the delta is the
  statutory engine both directions + agentic provenance + approval gates.
- **I3** — "payment-behavior memory" was a mean; upgraded to median+IQR.

## Shipped (P1→P8)
- **P1 honesty pass** — README integration-status table (live/fixture/
  sandbox/roadmap), real guardrail paths in CLAUDE.md, implemented-vs-planned
  tool list.
- **P2 tally@v1 connector** — real TallyPrime HTTP-XML protocol: Export
  envelopes, TDL ledger collection, **flat-sibling BILLFIXED/BILLCL/BILLDUE
  parsing**, debit-negative → positive-paise normalization, `1-Apr-2026` +
  `YYYYMMDD` dates, injectable transport (stdlib urllib default — no new
  deps), push_voucher refuses without approval_token *before I/O*. 9 tests.
- **P3 Payables Shield** — bills table (migration 0012) mirroring invoices;
  pure `services/payables.py`: §15 bands (within/closing/breached), §16
  interest owed, 43B(h) disallowance exposure, **FY-end on the IST calendar**
  (UTC date alone misplaces 31 Mar evening). GET /payables/compliance +
  frontend page + nav + ⌘K. `medium` enterprises are OUTSIDE 43B(h) (micro &
  small only). MSME status is human-tagged, never inferred.
- **P4 enforcer reframe** — rungs are preparation states ("letter ready",
  "samadhaan ready"), radar copy = telemetry/leverage-held, letters unchanged
  (already CA-framed drafts behind the gate).
- **P5 forecast stats** — `behavior_stats` (median, IQR spread ≥4 obs);
  downside band widens per-client via `max(14d floor, spread)`; TReDS sandbox
  rate 1800→950 bps and injectable; bank-rate constant carries a re-verify
  protocol note.
- **P6 Tally pull-through + brief strip** — POST /books/imports/tally
  (fixture|live via settings `tally_mode`, **mode echoed in response** —
  demo data never masquerades), idempotent by bill number, audit-logged;
  "Pull from Tally" button; brief gains data-conditional 43B(h) strip.
- **P7 gates** — backend 40 · agents 48 · tools 23 unit; tsc/eslint 0;
  Playwright 24/24; prod build; contracts regen no-drift.
- **P8 pitch deck** — docs/product/FinDesk_Pitch_Deck.pptx, 10 slides,
  Liquid Ledger palette, repo-honest claims, validated + visual-QA'd.

## Gotchas (durable)
- **Same-flush FK ordering with asyncpg executemany**: parent Counterparty +
  child Bill added in one flush hit FK violation despite FK metadata — fix:
  `await session.flush()` right after creating the parent.
- **Alembic needs `.env` exported** (`set -a; source .env`) when run from
  `backend/` — Settings' env_file is cwd-relative, silently falls back to the
  default DB URL and fails auth.
- **pptxgenjs default valign is middle** on tall text boxes — card bodies
  float mid-card; set `valign: "top"` explicitly.
- **`make test` skips memory/** — memory has `tests/e2e` only now, the loop
  requires `tests/unit`.
- Seeded BILLS use fixed dates (like LATE_INVOICES) — bands drift as the
  demo ages; breached only gets more breached, so specs stay stable.
- Playwright strict mode: stat-card label + table header with identical text
  need `.first()`.
- The beam-pulse spec can flake in a full-suite run (order-dependent live
  run); passes isolated — re-run before blaming it.

## State at close
- Branch `feat/crucible-hardening` pushed (8 commits over 4529adf); PR not
  opened — human's call: https://github.com/Jee8825/FinDesk/pull/new/feat/crucible-hardening
- Suite: 111 unit + 24 Playwright (3 new payables specs).
- New surfaces: /payables/compliance, /books/imports/tally; migration 0012;
  settings tally_mode|tally_gateway_url|tally_company.
- Kill log (P6 exploration): GST recon (another mock, dependency lens),
  WhatsApp chase preview (aesthetics, not value), data-room export (good,
  deferred — lost to Tally pull-through on impact÷effort).
