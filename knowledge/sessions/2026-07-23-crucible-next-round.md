---
title: 2026-07-23-crucible-next-round
type: note
permalink: findesk/sessions/2026-07-23-crucible-next-round
---

# Session — 2026-07-23 — Next-round crucible: landscape re-scan + feature roadmap

Ran project-crucible (STRESS-TEST + DISCOVER) on the post-hardening repo.
Full report: `docs/product/crucible-next-round.md`.

## Landscape facts (July 2026)
- GST **IMS mandatory since 1 Apr 2026** — statutory ITC gate (Sec 38
  substituted Oct 2025). Accept/reject/pending now determines ITC.
- GSTR-3B **hard-locked** since Jul-2025 period; fixes only via GSTR-1/1A.
- **TallyPrime 7.0/7.1**: IMS surfacing, connected banking (Axis/SBI/ICICI),
  **TallyIra AI** (Jun 2026) — incumbent entered Module A's lane.
- AA/FIU gate unchanged (no FIU-Lite). DPDP rules notified 13 Nov 2025;
  hard enforcement ~May 2027.

## Verdict
Differentiate up-stack: gate + provenance + statutory math + forecast
fusion. Never race TallyIra at data entry.

## Roadmap (impact ÷ effort)
1. Claims pass (observability + AI language) — hours
2. **F1 IMS Copilot** fixture-first (`ims@v1` reserved; set_state ⚠) — 1–2 wk
3. **F2 month_end_close graph** (composition over existing endpoints) — 1–2 wk
4. F3 collections outcome loop — closes seed-only memory gap — 3–5 d
5. F4 Udyam Vendor Verify (msme_status is self-declared today) — 3–5 d
6. F5 glass-box run viewer (persist emitter.step events) — 3–5 d
7. W1 live-Tally banked proof — 1 d · W2 DPDP note — 1–2 d · F6 CA rollup — 1 wk

## Gaps found in current shape
- Collections graph has **no memory write-back** (behavior loop = seed-only).
- `Counterparty.msme_status` nullable self-declared string — shield scoping
  depends on it; commodity Udyam APIs exist (IDfy/AuthBridge/Deepvue).
- Docs claim Langfuse+OTel; **zero wiring** in code.
- `prompts/` has exactly one prompt; only recon imports llm.py.

## Kill log (closed directions)
Bharat Connect (BD-gated), einvoice cross-check (commodity), Zoho-now,
GSTR filing product (liability), UPI-links-as-feature, AA-now, NL→SQL chat,
WhatsApp channel, payroll module.

## Part 2 — Frontend & Backend layer audit (same day)

Report: `docs/product/crucible-layer-audit.md`. Backend: no Criticals.
Key fixes: FE1 forecast 6s-timer invalidate → stream run.done; FE2
useRunStream no-reconnect + done-on-error; FE3 cursor never sent (50-row
dead-end); B1 auth pack (no rate limit, stateless refresh) + FE4 cookie
migration = pre-pilot gate; B4 contract codegen CI (shapes hand-mirrored
both sides today). Layer CLAUDE.mds drifted from reality (5 claims listed
in report). SSE server path is production-grade — keep. Add-on build lists
for F1–F6 are in the report, per layer, with effort.
