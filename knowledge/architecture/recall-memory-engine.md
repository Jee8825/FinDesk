---
title: recall-memory-engine
type: note
permalink: findesk/architecture/recall-memory-engine
---

# Recall Memory Engine (`memory/` — vendored)

The **product's** memory service (payment behaviors, vendor beliefs, conflict
math) — distinct from the agent/dev memory layer this vault provides.

- FastAPI service (`memory/recall/api`), engine/consolidation/conflict/decay
  math in `memory/recall/core`. Postgres+pgvector, Neo4j, Redis.
- Backend talks to it via `backend/app/memoryclient.py`
  (`RECALL_BASE_URL`, dev default localhost:8000 / .env 18000).
- **Hard rule 5:** vendored — only touch `memory/prompts/`, provider config,
  and FinDesk extension modules. Core math changes need an ADR
  (see `docs/decisions/ADR-0003-…` for the pattern).
- Contract: `memory/contracts/api.md` + root `contracts/memory.md`.
- Its docker compose (`memory/docker-compose.yml`) currently fails when merged
  by `make up` (build context resolves `infra/Dockerfile.backend` wrongly) —
  known break, see [[system-overview]].