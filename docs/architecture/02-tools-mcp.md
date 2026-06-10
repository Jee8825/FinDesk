# 02 — Tool Layer (MCP)

**Owner:** Tool Layer · **Code:** `tools/` · **Contracts:** `contracts/tools.md`

All access to the outside world goes through **Model Context Protocol (MCP)
servers**. Tools are typed, contract-bound, tenant-scoped, and loaded
on-demand to preserve the agents' context budget. A tool is plumbing: it
fetches, normalizes, and submits. It holds **no business logic, no prompts, no
memory writes**.

## 1. Tool catalog

| Tool server | Purpose | India-specific notes | Failure fallback |
|---|---|---|---|
| `bank_statements` | Parse CSV/PDF/XLS statements into normalized transactions | bank-format quirks table per bank | manual upload always works |
| `account_aggregator` | Consent-based bank data pull (Setu/Finvu) | AA consent lifecycle (request → active → expiry) | fall back to `bank_statements` |
| `tally` | Read/write vouchers, masters, chart of accounts | Tally Prime XML/ODBC gateway | export-file import |
| `zoho_books` | Same surface for Zoho Books API | OAuth per tenant | export-file import |
| `gst_portal` | GSTR-1/3B/9 data, GSTR-2B pulls | OTP/session handling, rate limits | manual JSON upload |
| `ims` | Invoice Management System accept/reject/pend states | input-credit timing feeds forecast | read-only degradation |
| `einvoice` | NIC e-invoice fetch/validate | IRN as first-class source id | skip enrichment |
| `email` | Draft + send collection/escalation emails | DKIM domain per tenant | drafts-only mode |
| `treds` | Invoice listing/quote/discount on TReDS | RXIL/M1xchange/Invoicemart adapters | recommend-only (no listing) |

Every server lives in `tools/<name>/` with `server.py`, `schemas.py`
(mirroring `contracts/tools.md`), fixtures, and unit tests.

## 2. Contract rules

- Input/output schemas live in `contracts/tools.md` and are versioned
  (`tool_name@v2`). The agent sees the contract, not the implementation.
- **Changing an output schema without bumping the contract version is the
  single most-banned action in this repo** — it silently breaks every graph
  that consumes the tool.
- All amounts integer paise, all timestamps UTC ISO-8601, all records carry
  `source` provenance (`{kind, external_id, fetched_at}`).

## 3. Credentials & scoping

- Per-tenant credentials in the secrets store (dev: `.env`-mounted; prod:
  cloud secret manager). A tool call's `tenant_id` selects credentials —
  there is no "default account".
- Tools enforce scope server-side: a call carrying tenant A can never read
  tenant B even if the agent asks. Defense in depth with the data layer.
- Outbound side effects (email send, TReDS listing) require an
  `approval_token` minted by the backend's approval engine — a tool refuses
  consequential calls without one. This makes the guardrail *physical*: even a
  fully compromised prompt cannot send mail.

## 4. On-demand loading

Graphs declare which tools each step needs; the MCP client connects only those
servers for that step. Tool descriptions are kept terse — context spent on
tool schemas is context not spent on memory.

## 5. Reliability

- Idempotency keys on all writes (`run_id:step_id:n`).
- Retries with backoff inside the tool server (not in the graph), surfacing a
  typed `ToolError{retryable, reason}`.
- Every external call recorded as a child span with latency, status, and
  redacted request snapshot (reference pattern: payload ID, not payload).
