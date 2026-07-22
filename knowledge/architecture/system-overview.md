---
title: system-overview
type: note
permalink: findesk/architecture/system-overview
---

# System Overview

FinDesk — the **autonomous CFO for Indian SMEs**. Two modules: **A** autonomous
bookkeeping (ingestion, TDS-aware reconciliation, categorization, conflicts,
anomalies, receivables chasing, explainable reports) and **B** cash command
(payment-behavior memory, MSME 45-day enforcement, scenario forecast, TReDS
working-capital actions, credit data room).

## Flow in one breath
Frontend ([[frontend-ui]]) → Backend API ([[backend-api]], auth/approvals/SSE)
→ agent runs queued on **Redis streams** → LangGraph worker ([[agent-graphs]])
calls MCP tools + the Recall memory service ([[recall-memory-engine]]) →
deterministic **guardrails validate outside the LLM loop** → everything traced
+ appended to the hash-chained audit log.

## Folder map (repo root)
- `frontend/` Next.js 14 app · `backend/` FastAPI app · `agents/` LangGraph worker
- `tools/` MCP servers (`findesk_tools`) · `memory/` vendored Recall engine
- `shared/` generated contract models (`findesk-shared`) — never hand-edit
- `contracts/` source of truth (api.yaml, db.md, events.md, memory.md, tools.md)
- `prompts/` all LLM prompts · `infra/` docker/CI · `docs/` architecture + team

## Dev runtime (as actually used, 2026-07)
- Postgres 16 in docker on host port **15433** (override), Redis on **6380**.
- Backend: `./.venv/bin/uvicorn app.main:app --port 8080` **from repo root**
  (pydantic-settings reads `.env` relative to cwd — running from `backend/`
  silently uses wrong defaults).
- Worker: `./.venv/bin/python -m findesk_agents.worker`.
- Frontend: `npm run dev` in `frontend/` → port 3001; `/api/v1/*` is rewritten
  to `BACKEND_URL` (default localhost:8080) in `next.config.mjs`.
- The root `.venv` has backend/agents/tools/shared installed editable.
- Known break: `backend/Dockerfile` fails (`findesk-tools` not copied) and the
  combined `make up` fails resolving `memory/infra/Dockerfile.backend` — local
  venv is the working dev path.

## Hard rules (short form — full text in root CLAUDE.md)
contract-first · no money movement / no auto-send (approval gate) · prompts in
`prompts/` · no raw SQL outside repositories · memory/ core math untouched ·
tenant_id everywhere · Alembic migrations · money is integer paise.