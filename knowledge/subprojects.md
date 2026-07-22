---
title: subprojects
type: note
permalink: findesk/subprojects
---

# Subprojects — index notes only

Deep graphs/notes cover the primary app (backend + agents + frontend). These
are pointers, not deep dives.

- **memory/** — vendored Recall engine → [[recall-memory-engine]]. Own
  CLAUDE.md, own tests, own compose. Do not fork core math without an ADR.
- **tools/** (`findesk_tools`) — MCP servers for banks/AA, Tally, Zoho,
  GST/IMS, email, TReDS. Backend depends on it (missing from its Dockerfile —
  known break).
- **shared/** — generated contract models (`findesk-shared` py + ts). Never
  hand-edit; `make contracts` regenerates from `contracts/`.
- **prompts/** — every LLM prompt, loaded by name. No inline prompt strings
  anywhere else.
- **infra/** — docker/CI; `infra/docker-compose.override.example.yml` is the
  template for machine-specific port remaps (this machine: pg 15433).
- **docs/** — architecture deep-dives (`docs/architecture/01…07`), team
  process (`docs/team/agentic-coding.md`), product spec PDF, ADRs
  (`docs/decisions/`).