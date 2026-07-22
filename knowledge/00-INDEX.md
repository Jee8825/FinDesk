---
title: 00-INDEX
type: note
permalink: findesk/00-index
---

# FinDesk Knowledge Vault — Map of Content

Start here. This vault is the persistent memory layer for AI agents and humans
working on FinDesk. Recall first → work → write-through → session log.

## Architecture
- [[system-overview]] — one-breath architecture + folder map
- [[backend-api]] — FastAPI surface, auth, routes, response shapes
- [[agent-graphs]] — LangGraph worker, the 7 graphs, run/SSE lifecycle
- [[frontend-ui]] — Next.js app, ledger-paper design system, page map
- [[recall-memory-engine]] — the vendored memory service (product memory, not agent memory)

## Domain
- [[glossary]] — TDS, MSME 45-day clock, TReDS, paise conventions, tenancy

## Decisions (ADRs)
- [[0001-memory-context-layer]] — this vault + basic-memory + graphify + hooks

## Subprojects (index notes only)
- [[subprojects]] — memory/, tools/, prompts/, infra/, docs/

## References
- [[wireframes]] — Claude Design wireframes, chosen A-variants, design tokens

## Sessions
- `sessions/` — dated session logs; newest one is injected at SessionStart

## Protocol (the loop)
1. **Recall first** — `graphify query "<question>"` + basic-memory search before exploring.
2. **context7 MCP** for any external lib/API/version question.
3. **Write-through** — persist durable facts/decisions here as you learn them.
4. **Close** every session with a dated note in `sessions/`.