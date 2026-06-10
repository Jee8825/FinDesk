# FinDesk — The Autonomous CFO

> It doesn't just close your books. It defends your cash.

FinDesk is an autonomous finance-operations and cash-command agent for Indian startups, SMEs and MSMEs (10–200 employees). It sits **on top of** the books a business already keeps (Tally, Zoho Books) — it does not replace them.

**Module A — Bookkeeping Foundation** autonomously produces clean, conflict-free, provenance-backed books: ingestion, TDS-aware reconciliation, consistent categorization, cross-period conflict detection, anomaly detection, receivables chasing, explainable reporting.

**Module B — Cash Command Layer** turns those books into foresight and action: per-client payment-behavior prediction, MSME Act 45-day enforcement, living 4/13-week cash forecasts with confidence bands, TReDS-integrated working-capital actions, and a credit-ready data room.

Module A saves money. Module B saves the business.

## Repository layout (monorepo)

| Path | What lives here | Owner (see CODEOWNERS) |
|---|---|---|
| `frontend/` | Next.js 14 dashboard (books, forecast, radar, approvals) | Frontend |
| `backend/` | FastAPI app: auth, REST + SSE API, services, approval engine | Backend/API |
| `agents/` | LangGraph orchestration: Planner → Executor → Critic → Approval Gate | Orchestration |
| `tools/` | MCP tool servers: banks/AA, Tally, Zoho, GST/IMS, email, TReDS | Tool layer |
| `memory/` | **Recall memory engine** (vendored copy, FinDesk-tuned) | Memory & Context |
| `shared/` | Cross-layer types, constants, generated contract models | All (contract-gated) |
| `contracts/` | Versioned API / tool / memory / DB / event contracts — **source of truth** | Layer owners jointly |
| `prompts/` | Every LLM prompt in the system (none hardcoded, ever) | Orchestration + Memory |
| `infra/` | Docker, CI/CD, environments, observability config | Infra & DevOps |
| `docs/` | Architecture (per-layer deep dives), team process, ADRs | All |

## Quickstart (dev)

```bash
cp .env.example .env            # fill in provider keys (DashScope/OpenAI/Anthropic)
make up                         # full stack: app + memory + datastores
make dev                        # install workspaces for local hacking
```

Default dev ports: API `8080`, frontend `3001`, memory API `8000`, memory dashboard `3000`, Postgres `5432`/pgvector, Neo4j `7474`, Redis `6379`. If those collide on your machine, copy `docker-compose.override.example.yml` → `docker-compose.override.yml` (gitignored) and remap.

## Start here

1. [docs/architecture/00-overview.md](docs/architecture/00-overview.md) — the whole system on one page, then per-layer deep dives.
2. [docs/team/collaboration.md](docs/team/collaboration.md) — ownership matrix, branching, review rules.
3. [docs/team/agentic-coding.md](docs/team/agentic-coding.md) — **read before pointing any AI agent at this repo.**
4. [CLAUDE.md](CLAUDE.md) — the AI context file every member's agent loads first.

## Hard rules (the short version)

- The agent **never moves money** and never sends external communication unapproved. Maker-checker by construction.
- Contracts in `contracts/` change **before** code that depends on them. Breaking changes follow the protocol in `docs/team/collaboration.md`.
- All prompts live in `prompts/`. All SQL lives in each layer's repository module. No vendor SDK imports inside engine/agent logic — providers are behind protocols.
- `memory/` is a vendored copy of [Recall](docs/architecture/03-memory-recall.md). Domain tweaks happen here; upstream stays untouched at its original location.

## License

Proprietary — internal hackathon/product work. Vendored `memory/` engine is Apache-2.0 (see `memory/`).
