# API Contract (v1)

Base URL: `http://localhost:8000`. Full machine-readable spec: `GET /openapi.json`.

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/memory/ingest` | `{user_id, session_id, content, scope?, team_id?, tenant_id?}` | `{units: MemoryUnit[], conflicts_detected}` |
| POST | `/memory/retrieve` | `{user_id, query, token_budget, scope?, team_id?, session_id?}` | `{memories: RetrievedMemory[], tokens_used, token_budget, cache_hit}` |
| GET | `/memory/{id}/why` | — | `{memory_id, confidence, status, explanation, evidence[], resolved_from[]}` |
| GET | `/memory/user-owned?user_id=` | — | `MemoryUnit[]` (GDPR-visible) |
| DELETE | `/memory/{id}?cascade=true` | — | `{deleted, provenance_nodes_removed}` |
| POST | `/memory/promote` | `{memory_id, scope, team_id?, is_orchestrator?}` | `{promoted}` · 403 on scope violation |
| POST | `/memory/prefetch` | `{user_id, session_id, recent_turns[]}` | `{predicted_cluster, staged}` |
| POST | `/admin/consolidate` | `{user_id, tenant_id?}` | `{tombstoned, compacted, crystallized_beliefs, procedural_created}` |
| GET | `/conflicts?user_id=` | — | `Conflict[]` |
| GET | `/stats?tenant_id=` | — | tier counts, conflicts, prefetch hit-rate, redis health |
| GET | `/health` | — | `{status: "ok"}` |

**Hard rule:** never change a response shape without bumping this contract and
the OpenAPI version. Frontend and SDK depend on these shapes.
