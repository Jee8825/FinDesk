# frontend/ — Interface Layer Context

Read root `CLAUDE.md` first. Deep-dive: `docs/architecture/07-frontend.md`
(page map, signature surfaces, quality bars).

Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui + TanStack Query.

## Rules for agents working here
1. API access ONLY through `src/lib/api.ts`: paths come from the generated
   `src/lib/generated/api-paths.ts` (never hardcode a route); response types
   in api.ts mirror `contracts/api.yaml` by review. If the endpoint you need
   doesn't exist, the change starts in `contracts/api.yaml`, not here.
2. Pages live under `src/app/(app)/<area>/`; shared primitives in
   `src/components` (`ui.tsx` kit + feature components). Components PascalCase.
3. Every page is a client component today (auth'd dashboard; tokens are
   client-side) — reads go through TanStack Query. Live agent progress via
   `useRunStream(runId)` (reconnecting SSE) or `useGraphRun(graph, keys)`
   for start-run→invalidate-on-done surfaces.
4. Never compute financial values client-side — backend is the truth; format
   with `formatINR` (integer paise in, lakh/crore grouping out), IST at the edge.
5. Every feature PR includes loading/empty/error states; signature surfaces
   (conflict card, forecast, radar, approvals, Why? drawer) hold WCAG 2.1 AA.
6. No direct calls to the memory service, tools, or Langfuse from the browser.

## Memory & Context Protocol (frontend addendum)

Recall first: `graphify query` + the `knowledge/` vault (see root CLAUDE.md).
Frontend-specific notes: `knowledge/architecture/frontend-ui.md` (design
tokens, page→variant map, formatINR rules) and
`knowledge/references/wireframes.md` (Claude Design source). Use context7 for
Next.js/Tailwind/framer-motion API questions. Write new UI decisions through
to those notes in the same PR.
