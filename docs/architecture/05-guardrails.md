# 05 — Guardrails & Policy Engine

**Owner:** Orchestration + Backend jointly (policy changes need both reviews)
**Code:** `backend/app/guardrails/` (enforcement), `agents/policies/` (declarations)

Trust is the product. Guardrails are **deterministic code enforced outside the
LLM reasoning loop** (NeMo-Guardrails pattern): an agent cannot talk its way
past them, and a prompt injection cannot disable them.

## 1. The non-negotiables (hard policies)

| # | Policy | Enforcement point |
|---|---|---|
| P1 | **Never move money.** No payment initiation exists anywhere in the codebase — no tool has the capability. | capability absence (strongest guardrail: the tool doesn't exist) |
| P2 | **Never send external communication unapproved.** Email/TReDS/letters are draft-only until an `approval_token` exists. | tool servers refuse without token; backend mints tokens only from human decisions |
| P3 | **Never commit a contested or low-confidence entry.** Open conflict or confidence < floor ⇒ approval queue. | commit service checks before ledger write |
| P4 | **Never breach our own 45-day obligations.** Payables re-timing (B4) must keep MSME-vendor payables inside statutory limits. | statutory clock engine veto on `wc_actions` |
| P5 | **Tenancy isolation.** No cross-tenant read/write anywhere. | RLS + tool-server scoping + memory tenant keys |
| P6 | **Legal-adjacent framing.** Interest computations and Samadhaan documents are *preparations*, flagged "review with your CA"; the system never files. | document generator templates + UI copy + no filing tool |

Policies are versioned data (`agents/policies/*.yaml`) compiled into the
enforcement engine; every verdict (pass/veto + rule id) is recorded on the
approval row and the trace. **A policy change requires an ADR + review from
both owning teams.**

## 2. Maker–checker by construction

The Indian-finance control expectation maps directly onto the architecture:

- **Maker** = Executor (drafts an action) · **Checker #1** = Critic (model)
  · **Checker #2** = policy engine (deterministic) · **Checker #3** = human
  approval for anything consequential.
- The approval queue is the *only* path to an `approval_token`; tokens are
  single-use, action-hash-bound, and expire.

## 3. Statutory clock engine

A pure, exhaustively unit-tested module (no LLM anywhere near it):

- Tracks the MSME Act 45-day window per receivable **and payable** (the Act
  cuts both ways), from acceptance date.
- Computes compound interest at the statutory rate (3× RBI bank rate) on
  overdue amounts — deterministic, to the paisa, with test vectors in
  `backend/tests/unit/statutory/`.
- Drives the escalation ladder (nudge → reminder → Act-referencing letter →
  Samadhaan prep) as *states*; the agent only chooses wording within the
  state, never the state transition rules.

## 4. Confidence floors

Per action class, tunable per tenant (conservative defaults):

| Action | Floor |
|---|---|
| Auto-commit a match/categorization | crystallized or ≥ 0.90 + Critic agree |
| Auto-book TDS-adjusted match | ≥ 0.85 + pattern seen ≥ 3 times |
| Anomaly card severity=high | evidence ≥ 2 independent signals |
| Forecast-driven alert | downside scenario, not point estimate |

Below floor ⇒ approval queue with the evidence attached. Floors live in
policy YAML, not prompts.

## 5. Prompt-injection posture

- Ingested documents and emails are **data, never instructions**: extraction
  prompts wrap them in delimited, role-isolated context.
- Tools that return third-party text mark it `untrusted=true`; graph nodes
  must not pass untrusted text into system prompts.
- Consequential actions can't be triggered by content anyway (P2's token
  requirement) — injection at worst wastes tokens.

## 6. Kill switches

- Per-tenant `agent_paused` flag (backend) — drains queues, freezes commits.
- Global read-only mode for incident response.
- Both are one `make` target away and audited.
