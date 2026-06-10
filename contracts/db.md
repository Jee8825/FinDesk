# App-DB Contract — v1

> **Implementation status:** migrations `0001` (identity + agent runs),
> `0002` (books: counterparties, bank_accounts, bank_transactions, invoices,
> matches, ledger_entries, audit_log, documents) `0003` (approvals queue
> with hash-bound single-use tokens), `0004` (conflict cards) and `0005`
> (chart_of_accounts + transaction categorization) are live. Tables carry the subset of
> columns their shipped features need (e.g. `invoices` gains gst/tds/irn in
> Phase 3); this file describes the target shape.

Human-readable schema reference for the app database (Postgres 16).
Authoritative DDL is the Alembic migration chain in
`backend/app/db/migrations/`; this file is the reviewed summary that changes
in the same PR as any migration. Conventions: PK `id UUIDv7`; every table has
`tenant_id` (FK, RLS), `created_at`, `updated_at` (UTC); money `BIGINT` paise.

## Identity & tenancy
- **tenants**: name, gstin[], udyam_no?, plan, parent_tenant_id? (multi-entity)
- **users**: email, password_hash, totp_secret?
- **memberships**: user_id, tenant_id, role `owner|accountant|ca|viewer`
- **counterparties**: kind `vendor|client|both`, name, gstin?, msme_status?,
  tds_section_default?, contacts jsonb

## Books (Module A)
- **bank_accounts**: bank, account_ref, source `upload|aa|api`
- **bank_transactions**: bank_account_id, external_ref, value_date,
  amount_paise, direction `cr|dr`, narration, dedupe_hash (unique per account),
  source jsonb
- **invoices** / **bills**: counterparty_id, number, issue_date, due_date,
  acceptance_date?, amount_paise, gst jsonb, tds jsonb, irn?, status
- **expenses**: counterparty_id?, date, amount_paise, category_code?, document_id?
- **matches**: bank_transaction_id, target (invoice|bill|expense + id), kind
  `full|partial|fee|tds_adjusted`, confidence numeric, matched_by `agent|human`,
  critic_verdict jsonb, status `proposed|committed|rejected`
- **ledger_entries**: entry_date, lines jsonb (double-entry, sums to zero),
  origin (match_id|manual|adjustment), committed_by, why_ref
- **chart_of_accounts**: code, name, type, parent_code?
- **conflicts**: claim_kind, claim_a jsonb, claim_b jsonb (each {content,
  confidence, evidence_refs}), hypotheses[], status `open|resolved`,
  resolution jsonb?, resolver_id?, memory_conflict_id
- **anomalies**: kind `duplicate|overcharge|out_of_pattern`, severity,
  evidence jsonb, recommended_action, recoverable_paise?, status
  `open|accepted|dismissed|recovered`

## Cash (Module B)
- **payment_observations**: invoice_id, promised_date?, paid_date?,
  nudge_at[]?, paid_after_nudge_days?
- **statutory_clocks**: target (invoice|bill + id), acceptance_date,
  day_count, due_45_date, overdue_days, accrued_interest_paise,
  escalation_level `none|nudge|reminder|act_letter|samadhaan_prep`
- **forecasts**: version, horizon `4w|13w`, scenario `base|upside|downside`,
  generated_at, run_id
- **forecast_lines**: forecast_id, week_start, inflow_paise, outflow_paise,
  closing_paise, drivers jsonb (traceability to invoices/behaviors)
- **wc_actions**: kind `treds|collect|retime`, unlock_paise, cost_paise,
  detail jsonb, rank, status `proposed|approved|executed|rejected`,
  policy_verdicts jsonb

## Control plane
- **approvals**: action_kind, action_payload jsonb, action_hash, requested_by
  (run_id, step_id), policy_verdicts jsonb, status
  `pending|approved|rejected|expired`, decider_id?, decided_at?,
  token_id? (single-use)
- **agent_runs**: graph, params jsonb, status, checkpoint bytea?, started_at,
  finished_at?
- **agent_steps**: run_id, name, status, span_ref
- **audit_log**: *insert-only role*; actor (user|agent run), action, entity_ref,
  payload jsonb (redacted), prev_hash, row_hash
- **documents**: kind, object_key, content_hash, meta jsonb

## Invariants (enforced in code + CI checks)
1. No FK ever crosses tenants; RLS on all tenant tables in prod.
2. `ledger_entries.lines` sums to zero per entry (DB CHECK via trigger).
3. `matches.status='committed'` requires: no open conflict on the same
   counterparty+claim_kind AND confidence ≥ policy floor (service-enforced,
   audit-logged).
4. `audit_log` has no UPDATE/DELETE grants for any app role.
5. Books rows are never hard-deleted; offboarding uses the audited purge script.
