# Contracts — Source of Truth

Every shape that crosses a layer boundary is defined here **before** code
consumes it. `make contracts` generates typed models into `shared/` (Pydantic
for Python, TypeScript for the frontend); CI fails if generated output drifts
from these files.

| File | Governs | Owners (dual review on change) |
|---|---|---|
| `api.yaml` | Backend REST + SSE surface (OpenAPI 3.1) | Backend + Frontend |
| `tools.md` | MCP tool inputs/outputs, versions | Tools + Orchestration |
| `memory.md` | Recall identity mapping, claim kinds, retrieval params | Memory + Orchestration |
| `db.md` | App-DB schema reference (tables, invariants) | DB + Backend |
| `events.md` | Redis stream + SSE event shapes | Orchestration + Backend |

## Rules

1. Contract change merges before (or with) the first consumer of the change —
   never after.
2. **Breaking changes bump a version** and keep the old version until all
   consumers migrate (tracked issue). Protocol in
   `docs/team/collaboration.md` §3.
3. Shared conventions everywhere: money = integer paise; timestamps =
   UTC ISO-8601; IDs = UUIDv7 strings; every cross-layer payload carries
   `tenant_id`; every agent-originated payload carries `run_id` + `step_id`.
4. If a field isn't in a contract, it doesn't exist — reviewers reject
   invented fields regardless of whether the code works.
