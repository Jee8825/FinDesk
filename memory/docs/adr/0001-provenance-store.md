# ADR 0001 — Provenance graph in Neo4j; best-effort dual-write

## Status
Accepted.

## Context
Every memory tool stores *what* a belief says; none store *why* the system holds
it. Recall records the epistemic history of each belief — direct statements,
corroborations, contradictions, and conflict resolutions — as a graph. This is a
graph-shaped traversal problem (evidence chains, `RESOLVED_FROM` lineage,
cascade deletes) that is awkward in relational SQL.

## Decision
- Memory units, embeddings, conflict logs live in **Postgres + pgvector**.
- The provenance graph lives in **Neo4j**: `(:Belief)` keyed by Postgres
  `memory_id`; `(:Evidence)` nodes via `:SUPPORTS` / `:CONTRADICTS`; belief
  lineage via `:RESOLVED_FROM`.
- Writes are a **best-effort dual-write**, not a distributed transaction. The
  Postgres write is the source of truth; the Neo4j write is wrapped in a
  try/except (`ProvenanceService._safe`) and logged on failure. A provenance
  hiccup must never block a memory write.

## Consequences
- Graph queries (`why`, cascade delete) are simple Cypher.
- The two stores can drift if a Neo4j write fails. Mitigation (roadmap): a
  reconciliation sweep that replays missing `:Belief` nodes from Postgres
  `memory_units` and `conflict_log`. For GDPR, cascade delete runs against Neo4j
  first, then Postgres, so a failure leaves the auditable belief in Postgres to
  retry rather than orphaning evidence.

## Alternatives considered
- **Relational-only provenance** (adjacency tables): possible, but recursive CTEs
  for evidence chains are harder to evolve and visualize.
- **Single graph DB for everything**: loses pgvector's mature ANN search.
