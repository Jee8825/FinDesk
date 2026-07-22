---
title: 2026-07-22-design-v2-liquid-ledger
type: note
permalink: findesk/sessions/2026-07-22-design-v2-liquid-ledger
---

# Session — 2026-07-22 (evening) — Design v2 "Liquid Ledger" (autonomous run)

Full autonomous 8-phase run (user-approved via 8-question round, then
hands-off). Branch `feat/design-v2`, one commit per phase, every phase
pushed before the next began. Direction + research: [[design-v2]].

## Shipped (P0→P7)
- **P0** — merged PR #16, researched user-supplied repos: chose
  `@paper-design/shaders-react` (ambient) over `@shadergradient/react`
  (R3F-heavy); liquid-glass-js = CSS reference only; R3F pinned
  fiber8/drei9/three0.170 for React 18.
- **P1** — token flip (same names, new dark values → pages inherit),
  Space Grotesk / Instrument Sans / IBM Plex Mono, glass CSS recipe,
  fx.tsx (Aura MeshGradient, LiquidMark LiquidMetal F, LiveRing
  PulsingBorder), rebuilt ui.tsx (API unchanged), glass shell, login.
  **Signature: the ledger beam** (amber→violet→teal header refraction,
  `[data-agent-live]` pulse hook).
- **P2** — 12-file mechanical sweep + charts recolored to the
  dataviz-validated palette (base #ffa028 / up #2dd4bf / down #a78bfa;
  gap markers claret = status, never series).
- **P3** — ⌘K palette (cmdk): nav > actions ranking (Playwright caught
  the inverted default), txn search → `/books?why=<id>` deep link.
- **P4** — 3D Cash Terrain (R3F): scenario heightfield + ₹0 claret
  waterline, hover drivers, gap beacon, WebGL/reduced-motion → 2D
  fallback + manual toggle.
- **P5** — Daily CFO Brief `/brief`: IST greeting, sparkline, MSME
  interest accrued, chase-list with enforcer escalation pills, agent
  activity, forecast narrative. Zero new backend.
- **P6** — Scenario Sandbox: contract-first `POST /forecast/whatif`
  (pure paise math, clamped params, 7 unit tests) + sliders + white
  ghost ridge/line in terrain + 2D chart. UI never computes money.
- **P7** — audit: `color-scheme: dark` (native selects!), themeColor,
  terrain aria, faint token lifted #6c7490→#7d86a6 (3.92→5.03:1 AA),
  prod build (shared 87.4kB, three.js lazy-chunked).

## Gates at ship
ruff clean · 120 unit tests (backend 33, agents 44, tools 13,
memory 30) · contracts regen no drift · openapi valid · tsc 0 ·
eslint 0 · Playwright **18/18** · `npm run build` ✓.

## Gotchas (durable)
- **Tailwind config / root-layout font changes need a dev-server
  restart** — HMR serves stale tokens ("Times" font, old hex) and it
  looks like broken CSS. Move `.next` aside + restart when tokens change.
- **`npm run build` while the dev server runs clobbers `.next`** → dev
  server 500s → Playwright auth setup fails and everything skips.
  Restart the preview after prod builds.
- **Browser-pane MCP throttles rAF when occluded**: delayed framer
  tweens strand at frame 0 (page reports visible!), pointer clicks
  drop, WebGL screenshots read black. Truth channel = Playwright
  (real Chromium): specs + `page.screenshot()`.
- **Design rule from the strand bug**: entrance staggers ship as CSS
  with `animation-fill-mode: both` (`.stagger-kids`), never delayed JS
  tweens — background tabs can strand those too.
- drei `Line` + `keyof Rows` widening: optional rows break
  ROW_Z/ROW_COLORS lookups — keep literal unions for required rows.
- `getByText` can't match `<input value=…>`; PulsingBorder/LiquidMetal
  prop schemas discoverable via `*Presets`/`*Meta` exports.

## Residuals — CLOSED same session (R1–R4, user-directed follow-up)
- **R1** — beam live: shell polls shared `["runs"]` cache, stamps
  `[data-agent-live]`; palette invalidates on startRun for instant pulse.
- **R2** — sandbox deep links: `/forecast?delay=&cut=&burn=` hydrate the
  sliders; debounced state mirrors back via router.replace.
- **R3** — light theme: tokens re-plumbed to CSS vars (`:root` dark,
  `[data-theme=light]` warm-paper overrides), `--fill-*` translucent
  fills, `--chart-*` themed marks, `--accent-contrast` CTAs, no-flash
  script, Settings Appearance card (localStorage `fd-theme`, dark
  default). All light pairs AA-verified (text ≥4.68, marks ≥4.88 vs 3.0).
- **R4** — `.github/workflows/e2e-nightly.yml`: pg16+redis7 services,
  alembic+seed, backend+worker headless, **fixture statement imported
  through the real /books/imports pipeline** (fresh DBs have no bank
  feed — seed creates tenants/invoices only), prod build, Playwright
  suite. Recall deliberately absent — dead RECALL_BASE_URL +
  `E2E_LITE=1` skips the badge-live spec. **Proven green: 20 passed,
  1 skipped in 48s** (6 iterations to get there). Cron 03:00 IST +
  workflow_dispatch (registers once the file reaches the default
  branch).

### CI e2e gotchas (hard-won, run 1→6)
- Local packages install in dependency order: `shared/py → tools →
  backend → agents` (pip can't resolve findesk-shared/-tools from PyPI).
- **Never run the suite against `next dev` in CI** — cold compiles on a
  2-core runner starve 5s expect timeouts (three.js chunks worst).
  Prod build + `npm run start` via `E2E_PROD=1` webServer switch.
- Specs must not assume accumulated data: the bank feed only exists
  after an import; the recovered-strip only after decided anomalies.
  Import a fixture through the product's own pipeline, poll the feed,
  and write data-conditional assertions.
- `reporter: "github"` writes no playwright-report/ — the failure
  artifact upload needs the html reporter if reports are wanted.
- workflow_dispatch doesn't register until the file exists on the
  default branch — prove new workflows with a temporary push trigger.

## Remaining after this session
- PR #17 review + merge into dev is the human's call.
- Suite count at close: 21 specs (20 in lite CI).
