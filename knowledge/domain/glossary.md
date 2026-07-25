---
title: glossary
type: note
permalink: findesk/domain/glossary
---

# Glossary — FinDesk domain terms

- **TDS** — Tax Deducted at Source. Clients pay invoices minus TDS (e.g. 2%,
  sections 194Q/194C); reconciliation must match `amount + tds_paise` to the
  invoice ("TDS-adjusted match", `kind: tds_adjusted`).
- **MSME 45-day clock** — Under MSMED Act 2006 §15, buyers must pay MSME
  suppliers within 45 days of acceptance. Past due, interest accrues at **3×
  the RBI bank rate**, compounded monthly. Drives [[backend-api]]'s radar and
  the `enforcer_45day` graph.
- **Escalation ladder** — `none → nudge → reminder → act_letter →
  samadhaan_prep` (MSME Samadhaan is the statutory dispute portal).
- **TReDS** — Trade Receivables Discounting System; invoices are auctioned for
  early payment at an annualized discount rate. FinDesk only ever *drafts* a
  `treds_listing` approval.
- **Paise** — all money is integer paise (`amount_paise`); ₹1 = 100 paise;
  1 lakh = ₹1,00,000; 1 crore = ₹1,00,00,000. UI shows lakh/crore compact.
- **Tenant** — one SME company. CA firms hold memberships in many tenants;
  every query/tool/trace carries `tenant_id` + acting `user_id`.
- **Conflict card** — two contradictory memory claims (stored belief vs new
  observation) surfaced for one-tap human resolution; the agent never
  silently overwrites a contested belief.
- **Why? / provenance chain** — every reported figure links to the
  hash-chained audit events that produced it (`/why/{entity}/{id}`).
- **FinDesk Score** — 0–100 credit-readiness rollup in the data room
  (reconciliation/categorization coverage, audit integrity, receivables
  discipline, conflict hygiene, forecast freshness).