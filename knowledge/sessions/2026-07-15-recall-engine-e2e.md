---
title: 2026-07-15-recall-engine-e2e
type: note
permalink: findesk/sessions/2026-07-15-recall-engine-e2e
---

# Session — 2026-07-15 (later) — Recall engine live + memory-in-the-loop e2e

## What happened
- **Recall memory engine brought up** (local-venv recipe, compose api image
  still unbuilt): `cd memory && docker compose up -d postgres neo4j redis`
  (ports **15432 / 7687 / 16379**, volumes findesk_pgdata/findesk_neo4jdata),
  then from repo root the API on **:18000** (where root `.env`
  RECALL_BASE_URL points):
  `RECALL_POSTGRES_DSN=postgresql+asyncpg://recall:recall@localhost:15432/recall
  RECALL_NEO4J_URI=bolt://localhost:7687 RECALL_REDIS_URL=redis://localhost:16379/0
  RECALL_LOCAL_BASE_URL=http://localhost:8090/v1
  .venv/bin/uvicorn recall.api.app:app --port 18000` (cwd must import
  `recall`; run from memory/ or with it on path). Needed
  `pip install psycopg[binary] openai` in the venv.
- **Recreated the missing dev shim** `memory/infra/dev/embedding_shim.py`
  (referenced by memory/.env but absent): OpenAI-compat `/v1/embeddings`
  via model2vec `potion-base-8M` (256-dim) + prompt-aware
  `/v1/chat/completions` for the `dev-echo` model — extraction echoes the
  content as one fact (conf 0.9), conflict prompts always return
  `flagged` ("dev-shim: contradictory beliefs always flagged for human
  review" — matches the conflicts-page annotation), classify falls back to
  labels[0]. Run: `.venv/bin/python memory/infra/dev/embedding_shim.py`.
- **E2E with memory in the loop, all verified**: worker retrieve 200s (no
  more "recall skipped"); new Aug statement → run streamed all 8 steps →
  learn ingested 4 new memories (23→27: 3 vendor-category beliefs + a
  payment-behavior fact); Blue Tokai ₹60k credit auto-matched INV-2026-049
  (radar 5→4, overdue ₹5.7L→₹5.1L); conflicts page served from live engine;
  resolving one DELETEd the losing memory with cascade (24→23); new
  unmatched debits show RULE category suggestions from crystallized vendor
  memory. `scripts/smoke_memory.py http://localhost:18000` passes.

## Bugs found & fixed
- **Frontend never used the refresh token**: `request()` in
  `frontend/src/lib/api.ts` threw on 401 → after the 15-min access-token
  TTL every page showed error states. Added single-flight
  `POST /auth/refresh` retry, falling back to clearTokens + /login
  redirect. Verified live against an expired session.
- **Why?(transaction) always empty**: audit rows are keyed
  `match:<id>`/`document:<id>`/`run:<id>`, never `transaction:<id>`.
  `routes_why.py` now expands transaction/bank_transaction refs through
  `BooksRepo.matches_for_transaction` + `audit_for_entities` (response
  shape unchanged, no contract edit). Why? drawer on a matched txn now
  shows ledger.commit with critic verdict + hash.

## Open threads
- Compose `api`/`frontend` services for Recall still unbuilt (host-venv
  recipe above is the working path) — same class of break as root `make up`.
- memory_units for smoke-tenant accumulate one unit per smoke run; harmless.
- mypy not installed in the shared venv (ruff+tests are the working gate).
