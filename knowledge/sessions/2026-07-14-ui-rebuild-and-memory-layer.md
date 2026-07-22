---
title: 2026-07-14-ui-rebuild-and-memory-layer
type: note
permalink: findesk/sessions/2026-07-14-ui-rebuild-and-memory-layer
---

# Session — 2026-07-14 — Wireframe UI rebuild + memory/context layer bootstrap

## What happened
- **Frontend rebuilt** to match the Claude Design wireframes ([[wireframes]]):
  new "ledger paper" design system (IBM Plex, cream light / warm-black dark
  surfaces, burnt-orange accent), framer-motion animations everywhere,
  lucide-react icons. 18 screens: all A-variants. New pages: reconciliation,
  categorization, collections, onboarding, settings, ca. Everything wired to
  the real backend via the existing `src/lib/api.ts` (added `exceptions()`,
  `switchTenant()`, `formatINRCompact`, memberships on `me()`).
- **Verified end-to-end in the browser**: seeded demo tenant, dashboard KPIs,
  conflicts card stack, approvals dossier (real MSMED chaser drafts),
  45-day radar clocks, forecast bands, transactions table, reports, data room
  — zero console errors; `tsc` and eslint clean.
- **Memory layer bootstrapped** per [[0001-memory-context-layer]]: this vault,
  basic-memory project `findesk` (write→search round-trip verified),
  `.mcp.json`, graphify graph (1174 nodes / 2498 edges / 106 communities,
  deterministic AST build, `.graphifyignore` curation, 0 excluded-path leaks),
  CLAUDE.md protocol sections, SessionStart/SessionEnd hooks (both dry-run
  clean, exit 0).

## Durable facts learned (written through to topic notes)
- Dev runtime quirks (pg 15433 / redis 6380 / run uvicorn from repo root /
  broken Dockerfiles) → [[system-overview]].
- Contract facts (scenario keys, action kinds, escalation ladder, /me shape)
  → [[backend-api]].
- basic-memory 0.22 has no `sync` verb — MCP server syncs live; `reindex`
  for out-of-session edits. `graphify update <path>` bootstraps a full
  no-LLM graph and honors `.graphifyignore`.

## Open threads / next session should
- `make up` is broken two ways (backend Dockerfile missing `findesk-tools`;
  memory compose build-context) — fix or document as local-venv-only.
- Consider LLM semantic pass (`graphify extract --mode deep`) + community
  labeling on-demand when a Gemini key is available.
- Approve the `.mcp.json` basic-memory server prompt once in the next
  interactive session, and confirm SessionStart injection appears.
- Collections "Draft chasers" depends on the `collections` graph producing
  `send_email` approvals — verify with fresh seed data.