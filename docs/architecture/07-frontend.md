# 07 — Frontend Layer

**Owner:** Frontend/Interface · **Code:** `frontend/` · **Contracts:** `contracts/api.yaml` (generated TS client in `shared/`)

Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui. The frontend's
job is to make autonomous work **legible and controllable**: every agent
conclusion arrives as a card with evidence and a decision affordance, and any
number can answer "Why?".

## 1. Information architecture (pages)

```
/login · /onboarding (connect books → seed memory → first scan)
/                       Dashboard: cash position, runway, alerts, agent activity
/books
  /transactions         normalized feed, match states, exception list
  /reconciliation       live agent runs (SSE), residual queue
  /categorization       chart-of-accounts view, crystallized vendor mappings
/conflicts              conflict cards: both claims + confidence + one-tap resolve
/anomalies              duplicate/overcharge/out-of-pattern cards, recoverable-money flags
/receivables
  /radar                45-day clocks per invoice, accrued interest, escalation ladder
  /collections          drafted chasers awaiting approval, per-client tone
/forecast               4w/13w scenario chart with confidence bands, gap attribution
/actions                working-capital options (TReDS/collect/re-time), costed + ranked
/approvals              THE control surface: everything consequential waits here
/reports                month-end pack, GST summary — every figure has a Why? button
/why/[entity]/[id]      full-screen evidence trail (shared by reports & data room)
/dataroom               credit-ready exports, FinDesk Score, lender share links
/settings               integrations (Tally/Zoho/AA/email/TReDS), entities, team, plan
/ca                     multi-client console: cross-tenant queue rollup (CA role)
```

## 2. Component & state conventions

- Components PascalCase; feature folders under `frontend/src/features/<area>`
  mirroring the page map; shared primitives in `src/components/ui` (shadcn).
- Server Components for reads; client components only where interactive.
- Data layer: TanStack Query against the **generated** API client in
  `shared/ts/` — handwritten fetch shapes are banned (contract drift).
- Live updates: one SSE hook (`useRunStream(runId)`) renders agent progress;
  queue badges poll lightweight count endpoints.
- Money rendered from integer paise via one `formatINR` util (lakh/crore
  grouping); dates IST at the edge.

## 3. The signature surfaces

- **Conflict card (A4):** two claims side-by-side with confidence bars,
  hypothesis chips ("vendor changed services?"), one-tap resolution; shows the
  provenance both claims trace to.
- **Forecast (B3):** three scenario bands (not lines), week-7 gap highlighted,
  attribution sentence ("Origin Roasters' worsening delays account for 60% of
  the risk"), click-through to the invoices behind any point.
- **45-day radar (B2):** per-invoice statutory clock, accrued interest
  counter, current escalation rung, next prepared step — with the "review with
  your CA" framing on legal-adjacent artifacts.
- **Approval queue:** payload diff, policy verdicts, critic reasoning, memory
  evidence — enough context to decide in seconds; approve/reject never
  navigates away.
- **Why? drawer (A8):** transaction → rules → memories → resolutions chain,
  rendered as a readable trail; "export as evidence" feeds the data room (B5).

## 4. Quality bars

- a11y: WCAG 2.1 AA on the five signature surfaces minimum.
- Loading/empty/error states are part of every feature PR (cards have
  skeletons; queues have zero-states that explain what the agent does).
- Visual regression snapshots for the signature surfaces.
- No financial value ever computed client-side — the backend is the truth;
  the frontend formats.
