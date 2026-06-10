# Recall

> **Recall is the first open-source memory engine that models memory as a living system — where memories decay, reinforce, and self-organize, rather than accumulate indefinitely.**

Every other agent memory layer (Mem0, Zep, Letta, Cognee, Cloudflare Agent Memory) is **additive**: memory accumulates forever. Recall is the memory layer that knows how to **forget**. It sits *above* your agent framework — it does not replace it.

Recall is not just a store. It is an **epistemic system**: it models how confident the agent should be in a belief, tracks the evidence behind every belief, detects when beliefs contradict each other, and forgets what is no longer relevant.

---

## Why Recall is different

| Capability | Mem0 | Zep | Letta | Cognee | Recall |
|---|---|---|---|---|---|
| Passive decay | ✗ | ✗ | ✗ | ✗ | **✓** |
| Retrieval reinforcement | ✗ | partial | ✗ | ✗ | **✓** |
| Conflict detection + resolution | ✗ | ✗ | manual | ✗ | **✓** |
| Provenance graph (why a belief is held) | ✗ | ✗ | ✗ | partial | **✓** |
| Budget-aware retrieval | ✗ | ✗ | ✗ | filter only | **packer** |
| Three-tier cognitive model | ✗ | ✗ | partial | ✗ | **✓** |
| Automated procedural extraction | ✗ | ✗ | manual | ✗ | **auto** |
| Cross-session confidence | static | ✗ | ✗ | ✗ | **dynamic** |

## Core concepts

- **Three tiers** — *episodic* (raw events, short TTL) → *semantic* (durable facts) → *procedural* (learned workflows, near-permanent).
- **Two orthogonal axes** on every memory:
  - **Strength** (decay) controls *retrieval priority*: `S(t) = S₀·e^(−λt)`, boosted on each retrieval, tombstoned below threshold.
  - **Confidence** (epistemic) controls *how much to trust it*: accumulates with corroboration, drops on contradiction, crystallizes when certain.
- **Two LLM roles** — a *heavy* model (extraction, consolidation, conflict resolution) and a *light* model (retrieval scoring, compression, prefetch intent). Pluggable: Qwen (default), OpenAI, Anthropic, or local.

## Architecture

```
            ┌──────────── Recall Engine ────────────┐
 ingest ──► │ extract → conflict-check → persist     │ ──► Postgres + pgvector (units, vectors)
            │            └─ provenance write ────────┼──► Neo4j (evidence graph)
 retrieve ◄─┤ embed → vector search → score → pack   │ ◄── relevance × recency × strength
            │ (decay + reinforcement on every hit)   │
            │ consolidate (cron) · prefetch (Redis)  │
            └────────────────────────────────────────┘
```

## Quickstart

```bash
cp .env.example .env          # add your DASHSCOPE_API_KEY (or OPENAI/ANTHROPIC)
docker compose up             # postgres(pgvector) + neo4j + redis + api + frontend
# API:        http://localhost:8000/docs
# Dashboard:  http://localhost:3000
# Neo4j:      http://localhost:7474
```

Use it from Python:

```python
from recall.sdk import Recall

async with Recall("http://localhost:8000") as recall:
    await recall.ingest(user_id="u1", session_id="s1",
                        content="I deploy our backend on AWS with kubectl.")
    ctx = await recall.retrieve(user_id="u1", query="where do I deploy?", token_budget=800)
    for m in ctx.memories:
        print(m.content, m.score)
```

## Benchmarks

Reproducible, offline benchmarks (run `make bench`) that use the same engine math
as production:

| Benchmark | Metric | Baseline | Recall |
|---|---|---|---|
| Long-horizon recall | precision@5 with injected stale memories | 0.48 | **1.00** |
| Context efficiency | relevant facts in a 400-token budget | 4 | **7** |
| Forgetting curve | mean strength (retrieved vs untouched) | 0.11 | **0.14** (1.33×) |

Charts and methodology in [`benchmarks/README.md`](benchmarks/README.md).

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,qwen]"
ruff check . && pytest            # unit tests run without external services
pytest -m integration            # spins up Postgres/Neo4j/Redis via testcontainers
make bench                       # generate the three benchmark charts
```

## Repository layout

See [`docs/architecture.md`](docs/architecture.md). Key packages: `recall/core` (engine), `recall/providers` (pluggable LLMs), `recall/db` (Postgres + Neo4j + Redis), `recall/api` (FastAPI), `recall/sdk`, `recall/adapters`, `frontend/` (Next.js dashboard), `benchmarks/`.

## License

Apache-2.0.
