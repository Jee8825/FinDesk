# DB Contract (v1)

## Postgres (pgvector) — required fields
| Table | Key fields | Purpose |
|---|---|---|
| memory_units | id, tenant_id, user_id, tier, content, embedding(vector), strength, strength_updated_at, decay_lambda, confidence, status, scope, team_id, cluster, retrieval_count, created_at | memory + vectors |
| conflict_log | id, user_id, memory_a, memory_b, semantic_distance, resolution, resolved_belief, rationale, created_at | belief-evolution audit |
| sessions | session_id, user_id, context, last_active | session state |
| agent_runs / tool_calls | run_id/call_id, tool_name, input_json, output_json, duration_ms | execution audit (feeds procedural extraction) |
| prefetch_events | predicted_cluster, num_staged, consumed | prefetch hit-rate telemetry |

Indexes: HNSW (`vector_cosine_ops`) on `memory_units.embedding`; composite on (tenant_id, user_id, tier, status). Multi-tenancy via explicit `tenant_id`.

## Neo4j — provenance graph
- `(:Belief {memory_id, confidence, status})`
- `(:Evidence {evidence_id, type, session_id, weight, note})`
- `(:Evidence)-[:SUPPORTS|:CONTRADICTS]->(:Belief)`, `(:Belief)-[:RESOLVED_FROM]->(:Belief)`

**Hard rule:** all schema changes go through an Alembic migration (`make revision`).
Neo4j writes are best-effort and reconciled separately (ADR 0001).
