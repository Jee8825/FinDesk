# Recall Architecture

## Layers

```
 SDK / Adapters (LangGraph, LangChain, AutoGen)
        │  REST + SSE
 ┌──────▼───────────────────────────────────────────────┐
 │ FastAPI (recall/api)                                  │
 ├───────────────────────────────────────────────────────┤
 │ RecallEngine façade (recall/core/engine.py)          │
 │   ingestion · conflict · provenance · confidence      │
 │   decay · retrieval(budget-packer) · consolidation    │
 │   prefetch · scoping                                   │
 ├───────────────────────────────────────────────────────┤
 │ Providers (recall/providers)  — heavy + light LLM,    │
 │   embeddings. Qwen | OpenAI | Anthropic | local       │
 ├───────────────────────────────────────────────────────┤
 │ Datastores (recall/db)                                │
 │   Postgres+pgvector  ·  Neo4j (provenance)  ·  Redis   │
 └───────────────────────────────────────────────────────┘
```

## The two axes

| | Strength | Confidence |
|---|---|---|
| Controls | retrieval **priority** | how much to **trust** |
| Dynamics | `S(t)=S0·e^(−λt)`, ×r on retrieval | corroboration ↑, contradiction ↓, dormancy drift |
| Below threshold | tombstoned (soft delete) | hedged in agent response |
| Above threshold | — | crystallized (decay paused) |

They are **orthogonal and independently queryable**: a high-confidence but
decayed memory may not surface; a low-confidence but recent one may surface but
should be hedged.

## Request flows

**Ingest** — heavy LLM extracts facts → embed → (semantic) conflict check vs
existing → resolve (heavy LLM) → persist surviving belief → write provenance
(direct/contradiction/resolution) → return DTOs.

**Retrieve** — embed query → pgvector cosine search (scope-filtered) → score
`relevance × recency × strength` → budget-pack (compress lower-priority via light
LLM to fit `token_budget`) → reinforce retrieved units → return.

**Why** — read evidence chain from Neo4j → render plain-language explanation.

**Delete (GDPR)** — cascade-delete belief + derived evidence nodes from Neo4j,
then delete the Postgres row.

## Key design decisions
- **Postgres + Neo4j split.** Vectors/metadata in Postgres; the *epistemic graph*
  (why a belief is held) in Neo4j. See `docs/adr/0001-provenance-store.md`.
- **Provenance writes are best-effort**, not in the Postgres transaction; the
  graph is reconciled separately so a graph hiccup never blocks a memory write.
- **Budget-packing is an optimization**, not a filter: it maximizes information
  coverage within a token budget by compressing, not just dropping.
