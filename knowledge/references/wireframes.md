---
title: wireframes
type: note
permalink: findesk/references/wireframes
---

# Wireframes & Design References

- **Claude Design project** (source of truth for the UI):
  https://claude.ai/design/p/17caf567-3883-4391-ad2a-22e22636c51c?file=FinDesk+Wireframes.dc.html
  Files: `FinDesk Wireframes.dc.html` (dc-runtime interactive prototype,
  16 pages × 3 variants each), `support.js`, reference PNGs in `uploads/`.
- To view locally: fetch the .dc.html + support.js, inject React 18 UMD before
  support.js, serve statically (the "standalone" build exceeds the 256 KiB
  DesignSync read cap and arrives truncated).

## Chosen variants (2026-07-14) — A across the board
The prototype marks the A-variants as "signature surfaces": Dashboard
command-center, Transactions master table, Reconciliation run+residuals,
Categorization COA tree, Conflicts card stack (A4), Anomalies cards+rollup,
Approvals queue+dossier, Radar clock table, Collections drafts+preview,
Forecast band chart (B3), WC ranked cards (B4), Reports pack+drawer (A8),
Data Room score hero (B5), Onboarding stepper, Settings integration cards,
CA roster table.

## Design tokens
See [[frontend-ui]] — palette, fonts and the light/dark surface rule live in
`frontend/tailwind.config.ts` + `src/components/ui.tsx`.