# DPDP Posture (W2)

**Status:** design note — fixture-only data today, so no live obligations yet.
This document exists so the posture is *designed in* before the first real
tenant, not retrofitted after.

## The clock (verified July 2026)

- DPDP **Rules notified 13 Nov 2025** (Digital Personal Data Protection
  Rules, 2025).
- Consent-manager framework operational **Nov 2026**.
- Hard enforcement expected **~May 2027** (end of the 18-month transition);
  penalties up to ₹250 crore per breach.
- Sources: Shardul Amarchand insight note; India Briefing compliance
  timeline (both read Jul 2026 — re-verify before a pilot).

## Data inventory (what FinDesk would hold per tenant)

| Class | Where | Personal data? |
|---|---|---|
| Bank transactions, invoices, bills | Postgres (tenant-scoped) | Counterparty names/contacts — yes (business context) |
| Counterparty records | Postgres | Names, GSTIN, Udyam URN, contacts jsonb — yes |
| Behavior memories | Recall (pgvector/neo4j) | Client payment behavior tied to counterparty ids — yes |
| Users | Postgres | Email + argon2 hash — yes |
| Audit chain | Postgres (insert-only) | Actor ids; payloads follow the reference pattern (ids, not documents) |
| Uploads / outbox / receipts | `var/` (dev) → object storage (prod) | Statement files — yes |

## Posture already built (structural, not policy-text)

- **Tenancy everywhere** — every query/tool/memory call carries tenant_id;
  no cross-tenant reads (hard rule 6).
- **PII discipline** — no real financial data in fixtures/logs/traces
  (hard rule 9); reference-pattern payloads in the audit chain.
- **Purpose limitation by construction** — recommend-only agent; external
  sends require maker-checker approval; single-use hash-bound tokens.
- **Security controls** — argon2, refresh rotation + revocation, rate
  limits, request-ids, tamper-evident audit chain (`GET /audit/verify`).

## Gaps to close before first real tenant (the pre-pilot list)

1. **Erasure path** — books rows are never hard-deleted (rule 4); DPDP
   erasure requests need the audited offboarding purge to cover Recall
   memories + `var/` artifacts + uploads, with an erasure certificate
   entry in the audit chain (the chain records *that* data was purged,
   not the data).
2. **Notice + consent** — a plain-language notice at tenant onboarding
   (what is processed, why, retention); counterparty data is processed
   under the tenant's own compliance duty — the DPA between FinDesk and
   the tenant must say who is data fiduciary vs processor.
3. **Retention schedule** — statutory books retention (8 years under GST,
   6+ under IT Act) vs behavioral memories (no statutory basis — needs a
   defined decay/purge horizon; Recall's decay engine is the natural home).
4. **Breach notification runbook** — DPB notification duty; ties into the
   request-id + audit trail for forensics.
5. **FE4 cookie migration** — localStorage JWTs are the known pre-pilot
   security gate (layer audit) — do together with this list.

## One-line pitch answer

"Fixture data today; DPDP-ready by design — tenancy, purpose-limited
agent actions, tamper-evident audit — with the erasure/notice/retention
work scheduled as the pre-pilot gate, ahead of the May-2027 enforcement
cliff."
