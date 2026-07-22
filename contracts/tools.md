# Tools Contract — v1

MCP tool surfaces. Agents see these schemas, never the implementations.
Conventions: amounts integer paise; timestamps UTC ISO-8601; every call
carries `tenant_id`, `run_id`, `step_id`; every record returned carries
`source: { kind, external_id, fetched_at }`. Consequential calls (marked ⚠)
additionally require a valid single-use `approval_token`.

## bank_statements@v1
- `parse_statement(document_id) → { transactions: [NormalizedTxn], bank, account_ref, period }`
- `NormalizedTxn: { external_ref, value_date, amount_paise, direction: cr|dr, narration, counterparty_hint?, balance_paise? }`

## account_aggregator@v1
- `request_consent(bank_hints[]) → { consent_id, redirect_url, status }`
- `consent_status(consent_id) → { status: pending|active|expired|revoked, accounts[] }`
- `pull_transactions(consent_id, from, to) → { transactions: [NormalizedTxn] }`

## tally@v1 / zoho_books@v1 (mirrored surface)

Tally transport: TallyPrime HTTP-XML gateway (`http://<host>:9000`), Export
envelopes; responses normalized to the shapes below. Fixture-tested — no live
calls in CI. `list_invoices` reads Bills Receivable (Sundry Debtors),
`list_bills` reads Bills Payable (Sundry Creditors).

- `list_invoices(from, to, status?) → { invoices: [InvoiceRef] }`
- `list_bills(from, to, status?) → { bills: [BillRef] }`
- `get_chart_of_accounts() → { accounts: [Account] }`
- `push_voucher(VoucherDraft) → { external_id }`  ⚠ (writes to the books of record)
- `InvoiceRef / BillRef: { external_ref, party, bill_date, due_date?, amount_paise, outstanding_paise, source }`
  (amounts normalized positive; Tally's debit-negative sign convention is
  absorbed at the tool boundary; overdue/interest math is backend business
  logic, never computed here)
- `Account: { code, name, type }` — `type` is the Tally parent group verbatim
  (e.g. "Sundry Debtors"); `code` is the Tally GUID or name-derived ref
- `VoucherDraft: { voucher_type, date, narration, ledger_entries: [{ ledger, amount_paise, direction: cr|dr }] }`

## gst_portal@v1
- `pull_gstr2b(period) → { lines: [ITCLine] }`
- `return_summary(period) → { gstr1_status, gstr3b_status, liability_paise, itc_paise }`

## ims@v1
- `list_pending() → { invoices: [{ irn, supplier_gstin, amount_paise, state: pending|accepted|rejected }] }`
- `set_state(irn, state)` ⚠

## einvoice@v1
- `fetch_by_irn(irn) → { invoice: EInvoiceDoc }`

## email@v1
- `draft(to[], subject, body_md, thread_ref?) → { draft_id }`
- `send(draft_id)` ⚠ — requires approval_token
- `thread_events(thread_ref) → { events: [{ kind: delivered|opened|replied, at }] }`

## treds@v1
- `quote(invoice_id) → { platform, discount_rate_bps, unlock_paise, cost_paise, valid_until }`
- `list_invoice(invoice_id, quote_id)` ⚠ — requires approval_token

## Error shape (all tools)

`ToolError { code, retryable: bool, reason, external_status? }` — graphs
branch on `retryable`, never on message text.

## Versioning

Output schema changes ⇒ new `@vN` alongside the old one; remove old after all
graphs migrate (tracked issue). Adding an optional output field is non-breaking;
everything else is breaking.
