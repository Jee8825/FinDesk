# CLAUDE.md — Recall AI Context

> **FinDesk vendoring note:** this folder is a vendored copy of the Recall
> engine serving as FinDesk's memory layer. Upstream lives outside this repo
> and is never modified from here. FinDesk-specific changes are allowed ONLY
> in the extension surface — `prompts/`, claim-kind metadata, conflict export,
> seeding scripts, provider config (see `../docs/architecture/03-memory-recall.md`
> §3 and `../contracts/memory.md`). Core engine math (decay / confidence /
> conflict scoring) requires an ADR in `../docs/decisions/` before any change.

Runtime context for AI assistants working on this repo. Paste at session start.

## What this is
Recall — a **living memory engine for LLM agents**. Memory that **decays,
reinforces, self-organizes, and reasons about its own beliefs**, rather than
accumulating forever. It sits *above* the agent framework.

## Stack
- Core: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + Alembic
- Vectors + metadata: PostgreSQL 16 + pgvector
- Provenance graph: Neo4j 5
- Cache / working memory / prefetch: Redis 7
- LLM/embeddings: pluggable provider abstraction (Qwen default; OpenAI/Anthropic/local)
- Frontend: Next.js 14 + Tailwind + shadcn/ui
- Observability: Langfuse

## Architecture (two axes, three tiers, two LLM roles)
- Tiers: episodic → semantic → procedural.
- **Strength** (decay): retrieval priority. `S(t)=S0·e^(−λt)`, reinforced on retrieval, tombstoned below τ.
- **Confidence** (epistemic): trust. Corroboration ↑ (diminishing), contradiction ↓, dormancy drift, crystallize ≥ 0.95.
- LLM roles: **heavy** (extract/consolidate/resolve) + **light** (score/compress/intent).

## Folder map
- `recall/core/` — engine modules (decay, ingestion, retrieval, conflict, provenance, confidence, consolidation, prefetch, scoping, engine façade)
- `recall/providers/` — pluggable LLM/embedding providers (never import a vendor SDK in engine code)
- `recall/db/` — Postgres (models/postgres), Neo4j (neo4j_store), Redis (redis_client)
- `recall/api/` — FastAPI app + routes
- `recall/sdk/` — async HTTP client
- `recall/adapters/` — LangGraph / LangChain / AutoGen
- `frontend/` — Next.js dashboard
- `benchmarks/` — benchmark suites + charts
- `prompts/` — all LLM prompts (never hardcode prompts in logic)
- `contracts/` — versioned tool/memory/DB/API contracts

## Hard rules
- All prompts live in `/prompts`, loaded via `recall.core.prompts`.
- All SQL lives in `recall/core/repository.py` (engine modules stay ORM-free).
- Engine code depends on provider *protocols*, never a concrete vendor SDK.
- Provenance (Neo4j) writes are best-effort and must never block a memory write.
- DB schema changes go through Alembic (`make revision m="..."`).
- Tests: pure logic → `tests/unit`; anything needing datastores → `tests/integration` (testcontainers, marked `integration`).
- Config via `recall.config.get_settings()` — never read `os.environ` directly in engine code.

## Common commands
- `make dev` install everything · `make up` stack · `make test` unit · `make test-int` integration · `make bench` charts
