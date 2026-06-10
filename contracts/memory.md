# Memory Contract — v1

How FinDesk uses the Recall service (`memory/`). The engine's own REST shapes
are upstream (`memory/contracts/`); this contract governs the **FinDesk
identity mapping, claim taxonomy, and budgets** layered on top.

## Identity mapping

| Recall field | FinDesk meaning |
|---|---|
| `tenant_id` | company (app `tenants.id`) |
| `user_id` | scope key — see below |
| `session_id` | agent `run_id` (or `seed:<batch>` for historical seeding) |
| `scope` | `private` (counterparty-scoped) or `team` (tenant-wide patterns) |

Scope keys (`user_id`): `vendor:<counterparty_id>`, `client:<counterparty_id>`,
`user:<app_user_id>` (interaction/tone memory), `tenant:global` (workflows,
close procedures).

## Claim taxonomy (unit metadata `claim_kind`)

| claim_kind | Example content | Feeds |
|---|---|---|
| `vendor_category` | "CloudNINE is Software Subscription (crystallized)" | A3, A4 |
| `deduction_pattern` | "Client X deducts 2% TDS on payment" | A2 |
| `payment_behavior` | "Blue Tokai pays ~12 days late; <3 days after a call" | B1, B3 |
| `behavior_drift` | "Origin Roasters delays worsening: 8→15→22 days" | B1 alerts |
| `tone_preference` | "Vendor Y responds to formal reminders only" | A7, B2 |
| `anomaly_baseline` | "AWS bill is consistently ₹6,800/mo" | A6 |
| `workflow` | "Month-end close: steps that worked" (procedural tier) | all graphs |

Extraction prompts producing these live in `memory/prompts/` (FinDesk
extension), versioned like all prompts.

## Retrieval budgets (per graph node defaults)

| Node | token_budget | filters |
|---|---|---|
| reconciliation.match | 800 | counterparty scope + `deduction_pattern`,`payment_behavior` |
| reconciliation.categorize | 600 | `vendor_category` (crystallized first) |
| anomaly.scan | 1000 | `anomaly_baseline` per vendor |
| collections.draft | 600 | `tone_preference` + interaction episodic |
| forecast.distributions | 1200 | `payment_behavior` per open client |

## Conflict export

Backend polls `GET /memory/conflicts?status=open` (upstream surface) →
materializes `conflicts` rows → human resolution POSTs back the winning claim
+ rationale; Recall records resolution + provenance. The conflict card UI
never talks to the memory service directly.

## Invariants

- App code reaches memory **only** through `backend/app/memoryclient` or the
  graph helper in `agents/` — both stamp `tenant_id/run_id/step_id` and apply
  redaction.
- Ledger facts live in the app DB; memory holds *beliefs about patterns*.
  If a number must be exact (an amount, a date), it is read from the app DB,
  not from memory.
- Tenant offboarding calls Recall's atomic deletion for the tenant key.
