# tools/ — MCP Tool Layer Context

Read root `CLAUDE.md` first. Deep-dive: `docs/architecture/02-tools-mcp.md`;
schemas in `contracts/tools.md`.

MCP servers wrapping external systems: bank_statements, account_aggregator,
tally, zoho_books, gst_portal, ims, einvoice, email, treds.

## Rules for agents working here
1. Tools are plumbing: fetch, normalize, submit. NO business logic, NO
   prompts, NO memory writes, NO policy decisions.
2. `schemas.py` mirrors `contracts/tools.md` exactly. Changing an output
   schema = new `@vN` version in the contract FIRST; never mutate `@v1` in place.
3. Consequential operations (send, push_voucher, list_invoice, set_state)
   require a valid `approval_token` — refuse without it, no flag to disable.
4. Tenant credentials resolve from `tenant_id`; scope enforced server-side;
   idempotency keys (`run_id:step_id:n`) on all writes; retries with backoff
   live HERE, surfacing typed `ToolError{retryable, reason}`.
5. Every record returned carries `source: {kind, external_id, fetched_at}`;
   amounts integer paise; timestamps UTC.
6. Third-party text in responses is marked `untrusted=true` — never strip it.
7. Each server: `server.py`, `schemas.py`, `fixtures/`, unit tests against
   fixtures (no live calls in CI).
