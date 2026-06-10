# Events Contract — v1

Shapes for Redis stream messages and SSE events. All events share the envelope:

```json
{
  "event": "<name>@v1",
  "id": "uuid7",
  "tenant_id": "uuid7",
  "occurred_at": "2026-06-10T07:30:00Z",
  "run_id": "uuid7 | null",
  "step_id": "uuid7 | null",
  "payload": { }
}
```

## Streams

`agents:interactive` (user-triggered, low latency) · `agents:batch` (scheduled
sweeps). Consumer groups per graph type. At-least-once; consumers must be
idempotent on `id`.

## Job events (backend → agents)

| event | payload |
|---|---|
| `job.ping.requested@v1` | `{ params: {} }` — Phase-0 pulse check (Planner→Executor→Critic no-op) |
| `job.reconciliation.requested@v1` | `{ source: "ingestion"\|"schedule"\|"user", bank_account_id? }` |
| `job.anomaly_scan.requested@v1` | `{ period: "YYYY-MM" }` |
| `job.collections.requested@v1` | `{ }` |
| `job.enforcer_tick.requested@v1` | `{ }` |
| `job.forecast.requested@v1` | `{ debounce_key }` |
| `job.month_end_close.requested@v1` | `{ period: "YYYY-MM", requested_by: user_id }` |
| `run.resume@v1` | `{ run_id, approval_id, decision: "approved"\|"rejected" }` |

## Domain events (any → any, fan-out)

| event | payload |
|---|---|
| `ingestion.completed@v1` | `{ source_kind, document_id, txn_count }` |
| `ledger.committed@v1` | `{ entry_ids: [], match_ids: [] }` |
| `conflict.raised@v1` | `{ conflict_id, claim_kind }` |
| `conflict.resolved@v1` | `{ conflict_id, resolution, resolver_id }` |
| `anomaly.raised@v1` | `{ anomaly_id, kind, severity, recoverable_paise? }` |
| `approval.requested@v1` | `{ approval_id, action_kind, action_hash }` |
| `approval.decided@v1` | `{ approval_id, decision, decider_id }` |
| `forecast.updated@v1` | `{ forecast_id, gap_week?, gap_paise? }` |

## SSE events (backend → frontend, on `GET /agent/runs/{id}/stream`)

| event | payload |
|---|---|
| `run.step@v1` | `{ step_id, name, status: "started"\|"finished"\|"failed" }` |
| `run.tool@v1` | `{ step_id, tool: "name@vN", status, summary }` |
| `run.waiting@v1` | `{ approval_id }` |
| `run.done@v1` | `{ status: "succeeded"\|"failed"\|"cancelled", summary }` |

Breaking changes: bump the `@vN` suffix per event; emit both versions during
migration windows.
