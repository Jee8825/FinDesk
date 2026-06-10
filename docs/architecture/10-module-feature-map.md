# 10 — Module → Feature → Component Map

The spec's 13 features (A1–A8, B1–B5) mapped to the layers that implement
them. Use this to find where a feature lives, and to check a feature PR
touches all the right places.

## Module A — Bookkeeping Foundation

| Feature | Agents (`agents/`) | Tools (`tools/`) | Memory (`memory/`) | Backend (`backend/`) | Frontend (`frontend/`) |
|---|---|---|---|---|---|
| **A1 Ingestion** | — (event source) | bank_statements, account_aggregator, tally, zoho_books, einvoice | historical seeding scripts | import endpoints, normalization services, `documents` | /onboarding, /settings/integrations |
| **A2 Autonomous reconciliation** | `reconciliation` graph (match nodes) | tally/zoho (doc fetch) | deduction & payment patterns per counterparty | `matches`, commit service, exceptions API | /books/reconciliation |
| **A3 Categorization w/ consistency** | `reconciliation` graph (categorize node) | — | vendor-category beliefs, crystallization | chart-of-accounts service | /books/categorization |
| **A4 Cross-period conflict detection** | conflict-check node (write-time) | — | conflict engine + resolution history | `conflicts`, resolution API | /conflicts (cards) |
| **A5 Critic self-correction** | Critic node in every graph | — | consistency checks vs beliefs | critic verdicts on `matches` | shown in approval/run views |
| **A6 Anomaly detection** | `anomaly_scan` graph | — | per-vendor behavioral baselines + decay | `anomalies`, recoverable flags | /anomalies |
| **A7 Receivables chasing** | `collections` graph | email (draft+gated send) | relationship tone, interaction history | drafts + approval queue | /receivables/collections |
| **A8 Reporting + Why?** | `month_end_close` graph | gst_portal (summary data) | provenance why-chains | `/why/*` composition, report pack | /reports, /why/[entity]/[id] |

## Module B — Cash Command Layer

| Feature | Agents | Tools | Memory | Backend | Frontend |
|---|---|---|---|---|---|
| **B1 Payment behavior memory** | observation extraction in `reconciliation` | — | pattern crystallization, drift (worsening-trend) detection | `payment_observations` | client detail views, radar annotations |
| **B2 45-Day Enforcer** | `enforcer_45day` graph (wording within states) | email, document generation | tone calibration | **statutory clock engine** (deterministic), `statutory_clocks`, escalation ladder | /receivables/radar |
| **B3 Living cash forecast** | `cash_forecast` graph (attribution narration) | ims (input-credit timing) | B1 distributions consumed | scenario engine, `forecasts` | /forecast |
| **B4 Working-capital actions** | `working_capital` graph (option ranking) | treds | pay-on-nudge probabilities | `wc_actions`, P4 guardrail (own 45-day compliance) | /actions, /approvals |
| **B5 Credit-ready data room** | — | — | provenance graph is the asset | data-room exports, FinDesk Score, share links | /dataroom |

## Cross-cutting (every feature)

| Capability | Where |
|---|---|
| Planner–Executor–Critic | `agents/` core pattern (01) |
| Deterministic guardrails P1–P6 | `backend/app/guardrails` + `agents/policies` (05) |
| Approval gate + tokens | `backend/app/approvals` (06), /approvals UI |
| Provenance + audit | memory Neo4j + `audit_log` (08) |
| Tracing + evals | Langfuse/OTel + `infra/observability/evals` (08) |
| Tenancy & RBAC | everywhere (04, 06) |

## Feature PR checklist (the map as a gate)

A feature slice PR should normally touch: contract(s) → backend service/table
→ graph or node → prompt(s) in `prompts/` → frontend surface → tests at each
layer → eval fixture if it changes accuracy-relevant behavior. If your PR
skips a column the table says you need, explain why in the description.
