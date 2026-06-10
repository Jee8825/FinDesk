# Team Collaboration — Production Workflow

Team of 8, full-stack, AI-assisted. The structure below is what lets 8 people
*and* 8+ coding agents work simultaneously without stepping on each other.
Companion doc: [agentic-coding.md](agentic-coding.md).

## 1. Module ownership matrix

Owners are final decision-makers and primary reviewers for their layer —
ownership of decisions, not exclusivity of commits. Mirrored in
`.github/CODEOWNERS` so review requests route automatically.

| Members | Owns | Key responsibilities |
|---|---|---|
| 1 | **Agent Orchestration** (`agents/`, `prompts/agents/`) | graphs, planner/critic logic, model wiring, run lifecycle |
| 2 | **Tool Layer** (`tools/`, `contracts/tools.md`) | MCP servers, connector adapters, tool registry, credentials flow |
| 3 | **Memory & Context** (`memory/`, `contracts/memory.md`, `prompts/memory/`) | Recall service, FinDesk extensions, seeding, retrieval budgets |
| 4 | **DB & Storage** (`backend/app/db`, `contracts/db.md`, migrations) | schema, migrations, repositories, Redis strategy, data classification |
| 5–6 | **Backend/API** (`backend/`, `contracts/api.yaml`, `contracts/events.md`) | routes, services, auth/RBAC, approval engine, SSE |
| 7–8 | **Frontend** (`frontend/`) | dashboard, cards/queues, SSE rendering, generated-client usage |
| any 1 (rotating) | **Infra & DevOps** (`infra/`, `.github/`) | compose, CI, environments, observability pipeline |

Cross-layer items (guardrails, `shared/`) require review from *both* sides
listed in CODEOWNERS.

## 2. Branching (GitHub Flow, two protected branches)

```
main ← production-ready only (protected)
dev  ← integration branch (protected)
feat/<short-name> · fix/<…> · chore/<…> · docs/<…>
```

- Nobody pushes to `main` or `dev`. PRs into `dev`; release PRs `dev → main`.
- ≥ 1 review (CODEOWNER auto-requested) + green CI required to merge.
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`).
- AI-generated code gets **the same review scrutiny as human code** — no
  exceptions, no "the agent wrote it" in reviews.
- Keep branches < ~3 days old; rebase on `dev` daily. Stale parallel branches
  are the #1 multi-agent merge hazard.

## 3. Contract-first development

The #1 source of team conflict is shape drift: frontend expects what backend
doesn't return; a graph consumes a tool field that was renamed. Therefore:

1. **Contracts change first.** Any cross-layer shape change starts as a PR to
   `contracts/` (can be the same PR as the implementation, but the contract
   diff is reviewed by *both* affected owners).
2. `make contracts` regenerates `shared/` (Pydantic + TS types). CI fails if
   generated output doesn't match committed output.
3. **Breaking-change protocol:** announce in the dev channel with the contract
   diff → both owners approve → version bump (`@v2`) with the old version kept
   until consumers migrate → migration tracked as an issue. Silent breaking
   changes are revertable on sight.

## 4. Team rhythm

- **Daily (async, 5 min):** yesterday / today / blocked — in the dev channel.
- **Friday sync (30 min):** integration review on `dev`, CLAUDE.md updates
  (root + layer files), contract debt review, demo of the week's slice.
- **Weekly end-to-end smoke test:** one person runs the full flow on `dev`
  compose (`make smoke`): ingest fixture statement → reconciliation run →
  resolve one conflict → approve one email → forecast renders. The overlooked
  step that catches integration rot before it compounds.

## 5. What needs coordination vs what doesn't

| No coordination needed | Coordinate first |
|---|---|
| Changes inside your layer behind a stable contract | Anything touching `contracts/` or `shared/` |
| Adding tests, fixtures, docs for your layer | New env vars / compose services (infra owner) |
| New prompt versions (keep old until eval passes) | Policy changes in `agents/policies` (ADR + dual review) |
| UI polish inside a feature folder | Schema migrations (DB owner) · new external dependency |

## 6. Definition of Done (feature slice)

Contract updated → implementation in every required layer (see
[10-module-feature-map.md](../architecture/10-module-feature-map.md) checklist)
→ unit tests green → integration test if datastore-touching → trace spans
verified in Langfuse locally → loading/empty/error states for UI → docs
touched if behavior changed → demoable on `dev` compose with seed data.
