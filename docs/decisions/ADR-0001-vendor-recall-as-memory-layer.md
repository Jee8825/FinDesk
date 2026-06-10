# ADR-0001 — Vendor Recall as the Memory Layer

**Status:** accepted · **Date:** 2026-06-10

## Context

FinDesk's spec makes every feature memory-driven (crystallization, decay,
conflict detection, confidence, provenance). The Recall engine
(`/Users/Jee/Hackathon/Recall`, Apache-2.0) implements exactly this
two-axis/three-tier model as a standalone service with SDK and adapters.
Options: (a) depend on it as an external service repo, (b) reimplement inside
FinDesk, (c) vendor a copy into the monorepo.

## Decision

**Vendor a copy at `memory/`** (option c). Upstream is never modified from
this repo. FinDesk-specific changes are confined to an extension surface:
`memory/prompts/`, typed claim metadata, conflict export, seeding scripts,
provider config (see `docs/architecture/03-memory-recall.md` §3 and
`contracts/memory.md`).

## Consequences

- One repo for the team and its coding agents — the monorepo requirement for
  8-way parallel agentic work holds.
- Engine math changes require an ADR, keeping a future upstream-sync path
  realistic (diffs stay localized to the extension surface).
- Recall keeps its own datastores and compose unit; app code talks HTTP only —
  the engine stays swappable.
- License note: vendored code remains Apache-2.0 with attribution; FinDesk
  code around it is proprietary.
