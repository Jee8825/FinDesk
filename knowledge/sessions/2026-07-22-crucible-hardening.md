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

---

## Lap 2 (2026-07-23, same branch) — self-judgment + arch hardening

Judge pass over lap-1 output + foundations, then Q1–Q7. Full detail:
`docs/product/crucible-stress-test.md` lap-2 section.

- **Q1 worker**: stable consumer name + XPENDING/XCLAIM adoption (idle>60s) +
  dead-letter `agents:dead` after 3 deliveries, run marked failed. The PEL-
  orphaning hole (random consumer names) was the lap's biggest arch find.
- **Q2**: `statutory_bank_rate_bps` threaded Settings→clocks/payables; drift
  test pins the two defaults together.
- **Q3**: bills.outstanding_paise (0013); exposure on unpaid portion; re-pull
  refreshes/settles. **Live verification caught sync resurrecting a
  recon-paid invoice from a stale export** → "paid is terminal", disagreement
  = `status_conflicts` count, never overwritten.
- **Q4**: dated in-horizon bills land in their due week (all scenarios),
  superseding that vendor's statistical baseline (fuzzy label containment).
- **Q5**: Deduction Defense — closing by deadline, breached by daily §16
  bleed, affordability from latest forecast opening balance.
- **Q6**: GET /audit/verify recomputes the hash chain live; tamper test on 98
  real entries: broken_at → restore → valid. Data-room chip.
- **Q7**: agents/CLAUDE.md catalog implemented-vs-planned; enforcer no-recall
  documented deliberate; beam spec flake fixed (wait-for-quiet, seen 2×).

### Lap-2 gotchas
- First full Playwright run after a dev-server restart can fail ONE random
  spec on cold-compile latency; re-run settles it. CI (prod build) immune.
- asyncpg + SQLAlchemy same-flush parent/child FK: flush after parent (again).
- Audit tamper-testing live: sqlalchemy scripts MUST run inside the venv or
  the restore silently no-ops (hit once; chain re-verified after fix).

Gates at lap-2 close: **121 unit** (backend 43 · agents 54 · tools 24) ·
tsc 0 · eslint 0 · **Playwright 24/24** · prod build ✓ · no contract drift ·
migrations → 0013. 7 commits this lap.

---

## Lap 3 (2026-07-23) — trust artifacts + critic seat

- **R1** credit-pack export: `GET /dataroom/export` zip (summary.md with score
  table + audit head hash, 3 CSVs), pure builders in
  `services/dataroom_export.py`, download button. Judge catch en route:
  lap-2's verify_chain duplicated dataroom's walker → consolidated (audit.py
  canonical, dataroom adapts shape). `gather_items` moved to services/payables
  (shared route+export).
- **R2** forecast critic: `critic.py` pure invariants wired
  project→critic→persist; violation fails the run. Test lesson: a mid-chain
  point edit breaks TWO continuity links (edit + wake) — expect both.
- **R3** bill drivers: engine tags `kind:"out"`; gap attribution filters to
  inflows; terrain hover renders − vendor bills in claret; db.md documents
  absent-kind=inflow backward compat.
- Live proofs: forecast run through critic (succeeded), out-drivers persisted,
  narrative bill total = exact paise sum of all 6 open bills, credit pack 4
  files with verified chain head.
- Playwright gotcha refined: first 1-2 full runs after a dev-server restart
  can each drop one heavy spec (three.js compile) — warm then definitive.

Gates: **131 unit** (47/60/24) · 24/24 e2e · prod build · no drift.
Lap totals: lap-1 8 commits, lap-2 7, lap-3 4.
