# 08 — Observability, Audit & Evaluation

**Owner:** Infra & DevOps (pipeline) + Orchestration (instrumentation)
**Code:** `infra/observability/`, instrumentation in every service

Three distinct artifacts, often confused — we keep them separate:

| Artifact | Question it answers | Store | Mutability |
|---|---|---|---|
| **Traces** | what did the system do, step by step, how long, how much | Langfuse (OTel) | TTL'd |
| **Audit log** | what happened to the books/actions, attributable to whom | Postgres append-only | immutable |
| **Provenance** | why is this belief/number held | Neo4j (memory svc) | grows, atomic-delete |

## 1. Tracing (Langfuse + OpenTelemetry GenAI conventions)

- Every agent run is a root trace; spans for plan/step/tool-call/memory-call/
  critic/policy-verdict; model spans carry token counts, latency, cost,
  prompt name+version (never the raw financial payload — reference pattern:
  IDs that resolve inside the trusted store).
- `run_id`/`step_id`/`tenant_id` on every span — one join key across backend,
  agents, tools, and memory service.
- Frontend reports web-vitals + API timing to the same backbone.

## 2. Audit log

- Insert-only Postgres table written via a dedicated DB role that has no
  UPDATE/DELETE; rows hash-chained (`row_hash = H(prev_hash ‖ payload)`).
- Recorded: ledger commits, conflict/anomaly resolutions, approval decisions
  (+token ids), external sends, policy verdicts, config/policy changes, kill-
  switch flips, data exports.
- This is what makes the books defensible to a CA, auditor, investor, or
  lender — it exceeds SOC-2-style trail expectations by construction.

## 3. Evaluation harness (the accuracy moat is measured, not asserted)

Lives in `infra/observability/evals/`; runs in CI nightly and pre-release:

| Eval | Metric | Source |
|---|---|---|
| Reconciliation accuracy | auto-match precision/recall vs golden set | synthetic + anonymized fixtures |
| Critic uplift (A5) | errors caught by Critic ÷ total errors | logged critic verdicts |
| Categorization consistency (A3) | same-vendor category stability across periods | books snapshots |
| Conflict quality (A4) | true-conflict rate of raised cards | human resolutions |
| Forecast calibration (B3) | coverage of confidence bands (e.g. 80% band ≈ 80% hits) | forecast vs actuals |
| Payment prediction (B1) | MAE of predicted vs actual payment date | observations |

Calibration results are **published in-product** (spec: trust is the pitch) —
the eval harness output is a customer-facing artifact, so it is versioned and
reviewed like code.

## 4. Metrics & alerting

- RED metrics per service; queue depth/age per stream; approval-queue latency
  (human SLA); memory-service retrieval latency and budget utilization;
  cost per run by graph type.
- Alerts: failed runs > threshold, queue age, calibration drift, token-cost
  anomalies, audit-chain verification failure (pages immediately).

## 5. PII-safe posture

External observability stores hold **references, not payloads**. Redaction is
in the SDK wrapper (`shared/py/telemetry.py`), not left to each developer.
Trace sampling is 100% for agent runs (they're the product), lower for plain
HTTP reads.
