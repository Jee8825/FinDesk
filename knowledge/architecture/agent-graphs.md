---
title: agent-graphs
type: note
permalink: findesk/architecture/agent-graphs
---

# Agent Graphs (LangGraph worker, `agents/findesk_agents`)

Worker entrypoint: `python -m findesk_agents.worker` — consumes Redis stream
`agents:interactive`, emits run events on `agents:events` + pub/sub channel
`run:<id>` which the backend relays as SSE
(`GET /agent/runs/{run_id}/stream`, shapes in `contracts/events.md`).

## KNOWN_GRAPHS (backend `routes_agent.py` must match worker registry)
- `ping` — pulse check (Planner → Executor → Critic demo)
- `reconciliation` — statement import → match → categorize → conflict-check
- `anomaly_scan` — duplicates / overcharges / out-of-pattern
- `collections` — drafts chasers → `send_email` approvals
- `cash_forecast` — 13-week `downside/base/upside` scenario engine
- `working_capital` — ranked, costed WC options (TReDS / collect)
- `enforcer_45day` — advances statutory escalation rungs

## Pattern
Planner → Executor → Critic → **Approval gate**. Anything consequential exits
via an approval (`action_kind` in [[backend-api]]) with a single-use,
hash-bound token. Guardrails are deterministic code, never prompt text.

## Frontend hook
`useRunStream(runId)` (fetch-based SSE, because EventSource can't send the
Authorization header) — parses `data:` frames, run ends on `run.done@…`.