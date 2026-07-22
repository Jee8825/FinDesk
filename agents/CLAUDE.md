# agents/ — Orchestration Layer Context

Read root `CLAUDE.md` first. Deep-dive: `docs/architecture/01-orchestration.md`.

LangGraph state machines (Planner → Executor → Critic → Approval Gate) run by
workers consuming Redis streams. Graph catalog (implemented): ping,
reconciliation, anomaly_scan, collections, enforcer_45day, cash_forecast,
working_capital. Planned: month_end_close.

## Layout
- `graphs/<name>/` — `graph.py` (wiring only), `nodes.py`, `state.py` (typed)
- `llm.py` — provider-agnostic chat (OpenAI schema over httpx); every caller
  degrades deterministically when it returns None
- `worker.py` — stream consumer: stable consumer name, pending-entry adoption,
  dead-letter (`agents:dead`) after max deliveries — see contracts/events.md
- `tests/unit` — nodes pure-tested with fake tool/memory clients
- Guardrail *enforcement* lives in backend services + tool-layer token
  refusals (root CLAUDE.md rule 2); there is no policies/ dir here

## Rules for agents working here
1. Recall-before-reason: every executor node retrieves memory context (budget
   from `contracts/memory.md`) before calling tools. Deliberate exception:
   the enforcer — its ladder is engine territory and memory must never move
   a statutory rung.
2. No vendor SDK imports; no direct DB access (backend services only); no
   direct HTTP to external systems (MCP tools only).
3. Prompts load from `prompts/agents/<name>@vN.md` — never inline strings.
4. Consequential actions never execute here — they become approval requests.
   The graph structure routes them; policy YAML changes need ADR + dual review.
5. Every node is idempotent on `step_id` and stamps `run_id`/`step_id` on all
   tool/memory calls and spans.
6. New graph = new entry in `docs/architecture/01-orchestration.md` catalog +
   event shapes in `contracts/events.md`.
