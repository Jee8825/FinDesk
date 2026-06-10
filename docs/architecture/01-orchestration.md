# 01 — Orchestration Layer (LangGraph)

**Owner:** Agent Orchestration · **Code:** `agents/` · **Contracts:** `contracts/events.md`, `contracts/tools.md`

The orchestration layer turns goals ("close the month", "review cash") into
supervised agent runs. It is a set of **LangGraph state machines** executed by
workers consuming Redis streams. It owns *how* the agents think; it does not
own policy (guardrails), facts (app DB), or beliefs (memory).

## 1. The core pattern: Planner → Executor → Critic → Approval Gate

```
 goal ──► PLANNER ──► plan: [step₁ … stepₙ]
              │
              ▼  (per step)
          EXECUTOR ── recall (memory) ── act (MCP tools) ── propose result
              │
              ▼
           CRITIC ── independent validation against memory + books
              │
        ┌─────┴─────────┐
        ▼               ▼
   guardrails OK    disagreement / low confidence / contested
        │               │
        ▼               ▼
     COMMIT        APPROVAL GATE ──► human queue (frontend) ──► resume
```

- **Planner** (heavy model): decomposes a job into typed steps with declared
  tool needs and memory scopes. Plans are data (logged, replayable), not prose.
- **Executor** (heavy model): performs one step. Always *recall before reason*:
  retrieve budget-packed memory context first, then act through MCP tools only.
- **Critic** (separate pass, ideally different model config): re-derives the
  conclusion independently and checks consistency with memory and the ledger.
  The Critic is the accuracy moat (spec A5) — its decisions are logged with
  reasoning and feed the eval harness.
- **Approval Gate**: a state, not a prompt. Runs pause (LangGraph checkpoint +
  interrupt), a human decision arrives via the backend, the graph resumes.

## 2. Graph catalog

| Graph | Trigger | Steps (typical) | Consequential actions |
|---|---|---|---|
| `reconciliation` | ingestion.completed / nightly | match → categorize → conflict-check → book | commits ledger entries (gated by conflict/confidence) |
| `anomaly_scan` | post-reconciliation / on-demand | baseline recall → scan → rank → card | none (cards only) |
| `collections` | daily | overdue scan → tone recall → draft emails | external send (always gated) |
| `enforcer_45day` | daily clock tick | statutory state → interest calc → escalation step | letters/Samadhaan docs (always gated, draft-only) |
| `cash_forecast` | every ledger event (debounced) | B1 distributions → 3 scenarios → gap attribution | none (alerts only) |
| `working_capital` | forecast gap detected | option pricing (TReDS/collect/re-time) → rank | every action recommend-only, gated |
| `month_end_close` | user-initiated | composite: reconciliation → anomalies → GST pack → report | report publish (internal) |

Each graph lives in `agents/graphs/<name>/` with: `graph.py` (wiring only),
`nodes.py`, `state.py` (typed LangGraph state), and unit tests with fake
tools/memory.

## 3. State, checkpoints, resumability

- Graph state is a Pydantic model; serialized checkpoints go to Postgres so an
  interrupted run (approval wait, crash, deploy) resumes exactly where it
  paused.
- Every run has `run_id` (UUIDv7); every step has `step_id`. These IDs appear
  in tool calls, memory calls, spans, and the audit log — one join key across
  the whole system.
- Long waits (approval pending) park the run; the resume event comes from the
  backend over the same Redis stream.

## 4. Job transport (Redis streams)

- One stream per priority class (`agents:interactive`, `agents:batch`).
- Consumer groups per graph type; workers are stateless and horizontally
  scalable; at-least-once delivery + idempotent steps (steps check
  `step_id` before re-applying side effects).
- Event shapes are versioned in `contracts/events.md`.

## 5. Model roles and budgets

Mirrors Recall's heavy/light split, defined in `agents/models.py` behind a
provider protocol (no vendor SDK imports in nodes):

| Role | Used for | Notes |
|---|---|---|
| `heavy` | plan, execute, critic, conflict narration | temperature low; structured output |
| `light` | scoring, compression, intent detection | cheap + fast |

Token budgets are explicit per node (memory context budget, output cap) and
recorded on spans — context discipline is what keeps runs cheap and traceable.

## 6. What the orchestration layer must never do

- Call a vendor API directly (must go through `tools/`).
- Encode policy in prompts ("don't send emails") — policy is the guardrail
  engine's job; the graph *structurally* routes consequential actions to the gate.
- Write to the app DB except through backend service interfaces.
- Hardcode a prompt — all prompts load from `prompts/agents/…` by name+version.

## 7. Testing

- Unit: every node pure-tested with fake tool/memory clients (`agents/tests/unit`).
- Graph: scenario tests running whole graphs against recorded tool fixtures.
- Eval: critic accuracy and forecast calibration measured by the harness in
  `infra/observability` (see 08) — a step change in either blocks release.
