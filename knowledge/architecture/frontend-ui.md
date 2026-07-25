---
title: frontend-ui
type: note
permalink: findesk/architecture/frontend-ui
---

# Frontend UI (Next.js 14, `frontend/src`)

Rebuilt 2026-07-14 to match **FinDesk Wireframes.dc.html** (see [[wireframes]]).
Stack: App Router + TypeScript + Tailwind + TanStack Query + framer-motion +
lucide-react. Dev server port 3001.

## Design system — "ledger paper"
- Fonts: IBM Plex Sans (body) + IBM Plex Mono (labels/numbers) via next/font.
- Light surface (books/queues): canvas `#e6dbc5`, cards `#fdfbf5`, ink `#26241f`.
- Dark surface (approvals, radar, collections, forecast, WC, data room, CA):
  bg `#211f1b`, cards `#262420`, text `#f0eee8`.
- Accent burnt orange `#e8730a`; memory-blue `#4a6fa5` marks stored beliefs;
  moss/mint = success; claret/blush = danger.
- Tokens live in `tailwind.config.ts`; primitives in `src/components/ui.tsx`
  (`PageShell` sets a SurfaceContext; `Card`/`Pill`/`Bar`/`StatCard`/buttons
  read it — pages never pass a `dark` prop around).

## Page map (route → wireframe variant, all A-variants)
`/` Dashboard command-center · `/books` Transactions master table ·
`/reconciliation` run + residuals · `/categorization` COA tree + vendor
mappings · `/conflicts` card stack (signature) · `/anomalies` cards + rollup ·
`/approvals` queue + dossier (dark signature) · `/receivables` 45-day clock
table (dark signature) · `/collections` drafts + preview (dark) · `/forecast`
band chart (dark signature) · `/actions` ranked WC cards (dark) · `/reports`
pack + Why? drawer (signature) · `/dataroom` score hero (dark) · `/onboarding`
stepper · `/settings` integration cards · `/ca` client roster (dark) ·
`/login`, `/share` (lender view).

## Rules that bit us
- API access only via `src/lib/api.ts` over generated `api-paths.ts` — new
  endpoints start in `contracts/api.yaml`.
- Never compute financial values client-side; format paise with `formatINR` /
  `formatINRCompact` (lakh/crore).
- Collections page = approvals filtered to `action_kind === "send_email"`.
- Dashboard KPIs are composed client-side from forecast/radar/approvals
  queries (there is no `/dashboard` endpoint).
- Wide tables need `overflow-x-auto` on the Card + `min-w` on the table.