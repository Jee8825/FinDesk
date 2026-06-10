# Contracts

Versioned interface contracts — the API between people, not just services.
Change them through a proposal in `docs/proposals/` reviewed by the affected
layer owners (see the breaking-change protocol). The live REST contract is also
always available as OpenAPI at `GET /openapi.json` when the API is running.

| Contract | Defines | Owner |
|---|---|---|
| [api.md](api.md) | REST endpoints, request/response shapes | Backend |
| [memory.md](memory.md) | What is stored, tiers, the two axes | Memory layer |
| [db.md](db.md) | Tables, key fields, the Neo4j graph | DB layer |
