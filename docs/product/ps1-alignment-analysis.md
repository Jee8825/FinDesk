# Aligning FinDesk with PS1 — Hidden Subscription & Recurring Payment Leak Detector

**Date:** 2026-07-25 · **Branch:** `feat/crucible-hardening` @ `afcf12b`
**Question:** can FinDesk be made to align with PS1, and what would it actually cost?
**Scope note:** PS2 (round-up micro-investment) is excluded on architecture, not
effort — it requires moving the user's money, which hard rule 2 forbids by
design. Everything below is PS1.

`[V]` = verified against code or a live run this session.

---

## 1. The decision that comes first

PS1 as written is a **consumer** product. FinDesk is **B2B SME**. There are two
ways to close that, and they differ by an order of magnitude.

| | **Option A — B2B reframe** | **Option B — consumer pivot** |
|---|---|---|
| Pitch | "Vendor & SaaS spend leak detector for SMEs" | Personal subscription tracker |
| Keeps | tenancy, counterparties, categorization, approval gate, audit chain, Module B as bonus | almost nothing above the parser |
| Needs | 3 new detectors + a page + seed data | new entity model, SMS/email ingestion, drop all of Module B |
| Effort | ~5 days minimum credible | ~2–3 weeks |
| Competitive position | SME SaaS waste, larger amounts, statutory adjacency | competes with every other identical submission |
| Risk | a judge may read PS1 as strictly consumer | you ship a worse product late |

**Recommendation: Option A.** Two substantive reasons beyond effort:

1. **The money is bigger and the data is better.** An SME's recurring vendor
   spend is larger, denser, and already sitting in the books FinDesk ingests.
   Consumer statements are noisier and you would be inferring from less.
2. **Option B throws away the differentiated half.** Module B — the 45-day
   clock, TReDS, the IMS/ITC clock, the credit data room — has no consumer
   analogue. Under Option A it stays in the demo as evidence of depth. Under
   Option B it is dead code you cannot show.

State the reframe explicitly on the first slide rather than hoping nobody
notices. "PS1, applied to the business, where the leaks are bigger and the
consequences are statutory" is a stronger position than a hedge.

---

## 2. What genuinely transfers `[V]`

More than expected, and it is worth being precise about which parts.

| PS1 focus area | Status | Evidence |
|---|---|---|
| Automatic transaction categorization | **Done** | `reconciliation/categorization.py` — memory-first, rules-second. The rule table already contains `SAAS\|SUBSCRIPTION\|ZOHO\|GITHUB\|SLACK\|NOTION\|FIGMA → software_cloud`. Live DB: `software_cloud` is the largest debit bucket. |
| Statement ingestion (unstructured) | **Done** | `tools/findesk_tools/bank_statements` — CSV/XLSX, dedupe hashing, period detection, skipped-row accounting. Fixtures in `scripts/fixtures/statement_*.csv`. |
| Payee normalization | **Done** | `findesk_shared.vendor_slug` — noise-token stripping, shared by categorizer, anomaly scan and the correction endpoint so slugs never diverge. This is the join key a subscription detector needs. |
| Duplicate-charge detection | **Done, and not even asked for** | `detect_duplicates` — same vendor slug + amount within 7 days. Double-billing is recoverable money. |
| Per-item action plan | **Pattern exists** | `services/payables.py` (Deduction Defense) ranks items by a deterministic cost metric and attaches an action per row. A leak table is the same shape. |
| Cancel / downgrade / renegotiate | **Better than asked** | Approval gate + sandbox email tool: recommend-only drafts a human approves, with single-use `approval_token` refusals at the tool layer. A leak detector that auto-cancels is dangerous; this one structurally cannot. |
| Data available to the detector | **Sufficient** | `/internal/anomalies/context` returns **all** debits (no window — `books_repo.debit_transactions` has no LIMIT) with `value_date`, `amount_paise`, `narration`, `counterparty_hint`, `category_code`. Exactly the input a cadence detector needs. |

Also transferable and non-trivial to rebuild: SSE run streaming, the Run Viewer
glass box, the append-only audit chain, the approval maker–checker flow, and the
whole frontend design system.

---

## 3. The three real gaps

The feature list makes this look like "reuse the anomaly detector, add a UI."
That is wrong. The core detector is the wrong *shape* for the core requirement.

### Gap 1 — the price-creep blind spot `[V]` — the important one

`detect_deviations` fires only at `ratio ≥ OUT_OF_PATTERN_FACTOR` (1.25) against
a baseline that must itself be stable within `BASELINE_STABILITY` (0.25 relative
spread). Run against synthetic price hikes on the real detector this session:

```
case                               detected?  kind
--------------------------------------------------------------
SaaS +12% hike (typical creep)     no         —
SaaS +20% hike                     no         —
SaaS +24% hike                     no         —
SaaS +26% hike                     YES        out_of_pattern (ratio 1.26)
SaaS +50% hike                     YES        overcharge (ratio 1.5)
+15% hike, 5 months old            no         —
```

Typical SaaS increases are 5–20%. **Every one of them is invisible.** Worse, the
last row: a +15% hike that has persisted five months is still invisible, and the
elevated price has been absorbed into the baseline as the new normal. That is
*precisely* the phenomenon PS1 names — "price hikes they never noticed" — and
FinDesk currently normalizes it.

The reason is statistical, not a tuning mistake. Two different problems:

- **Spike** — an outlier against a stable central tendency. Ratio test. *What
  exists*, and correct for its purpose (dispute one overcharged bill).
- **Step change** — a sustained level shift in a time series. Changepoint
  detection. *What PS1 needs, and what is missing.*

Do not "fix" `detect_deviations` by lowering the threshold — that would flood
the anomaly queue with normal variance and break a working feature. Build a
second, differently-shaped detector.

### Gap 2 — no cadence detection `[V]`

`grep -riE "recurring|periodicity|cadence|interval"` finds only prose. Recurrence
today is inferred from **amount stability** (`_stable_baseline`, and the
forecast's `monthly_outflows` = "vendors with a stable spend baseline"), never
from **periodicity**. Nothing measures "every 30 days." A vendor billed twice at
the same amount three days apart looks as "recurring" as a monthly subscription.

### Gap 3 — the demo data has no recurrence `[V]` — the invisible blocker

```
bank_transactions:  18 debits · 14 credits · 2026-04-03 → 2026-09-06
vendors with >1 debit:  WEWORK BKC RENT (2).  That is the whole list.
```

**You cannot demo a recurring-payment detector on data containing no recurrence.**
This is not polish; it is a precondition, it is invisible on any feature list,
and it is the most likely way this pivot fails on stage. Budget for it as a
first-class work item (§7).

---

## 4. Detector designs

All three are pure, deterministic, test-vectored, no LLM — matching
`statutory.py` / `detection.py` house style.

### 4.1 `recurrence.py` — cadence

Group debits by `vendor_slug`, sort by `value_date`, take inter-arrival gaps.

- Require ≥3 occurrences (2 gaps) to say anything; ≥4 for confident cadence.
- **Normalize skipped periods before measuring dispersion.** For median gap `m`,
  divide each gap by `round(g/m)` — a gap of ~2m is one missed charge, not a
  cadence break. Without this, one skipped month destroys an obvious monthly
  series.
- Classify on the normalized median: weekly ≈7, fortnightly ≈14, monthly 28–31,
  quarterly ≈90, annual ≈365. Monthly needs an absolute tolerance (±4 days) not
  a relative one — billing drifts across weekends and month lengths.
- Dispersion above tolerance → `irregular`; exclude from drift detection.
- Emit `last_seen` and `next_expected`.

`next_expected` is load-bearing beyond cadence: if
`now > next_expected + tolerance` the series has **stopped** — already cancelled.
Those must be excluded from leaks, or the tool nags about things the user already
fixed, which is how these products lose trust.

### 4.2 `drift.py` — step change (silent price hikes)

For each vendor with a non-irregular cadence, over the amount series:

- Scan candidate split points; at each, compare `median(before)` vs
  `median(after)`, requiring ≥2 points per side and each side internally stable.
- Report a changepoint when `|Δ| / before ≥ MIN_DRIFT` (start at **0.05**).
- Emit `from_paise`, `to_paise`, `pct`, `effective_from` (date of the first
  post-change charge), and **`annualized_extra_paise = Δ × periods_per_year`**.

That last number is the product. Not "anomaly detected" but *"Notion went
₹1,000 → ₹1,150 in March — ₹1,800/year you never approved."*

**Guard usage-based vendors.** AWS varies every month by design; it will have no
stable level, land as `irregular`, and must be excluded from drift or it cries
wolf monthly. Report it in a separate lane ("usage-based, ₹X/mo average, trend
+Y%"). The live fixtures already contain AWS, so this case is not hypothetical.

**Seat-creep bonus, nearly free:** when successive amounts rise in discrete equal
steps, that is seat additions, not a price hike. Different action ("confirm
headcount — you are paying for N seats"), and computable from the step sizes.

### 4.3 `scoring.py` — the leak score

Must be deterministic and explainable — a score a user cannot interrogate is a
score they will not act on. Compose from independent, defensible signals, and
**show the components, never just the total**:

| Component | Source | Defensible? |
|---|---|---|
| `run_rate_paise` — annualized cost | cadence × amount | yes, arithmetic |
| `unapproved_drift_paise` — annualized increase | `drift.py` | yes, evidenced by date |
| `redundancy` — ≥2 active subscriptions sharing a `category_code` | existing `category_code` | yes, computable — and live data has 6 `software_cloud` debits |
| `duplicate_charges_paise` | existing `detect_duplicates` | yes, already shipped |
| `renewal_unreviewed` — annual cadence with a `next_expected` inside 60d | `recurrence.py` | yes, and actionable *before* the charge |

Rank by `run_rate + drift + duplicates`, exactly as `payables.py` ranks bills.

---

## 5. "Unused subscriptions" — the honest problem

PS1 asks for it. **It is not inferable from bank data.** Money leaving your
account tells you nothing about whether anyone logged in. Every submission that
claims otherwise is guessing, and a judge who has built this will know.

Three options, in ascending honesty:

1. Fake it with a proxy (flat spend, low amount) and hope. Don't.
2. Say it needs usage/SSO/seat data and scope it out. Acceptable.
3. **Turn the unanswerable inference into a memory-backed workflow.** Ask the
   user once per vendor — *"still using Figma?"* — store the answer in Recall as
   a belief with confidence and decay, surface it in the leak score, and re-ask
   when the belief ages out. Answers accumulate; the second month is better than
   the first.

Option 3 is the strongest move available and it is nearly free, because the
vendored Recall engine already does decay, confidence and conflict. It converts
PS1's hardest requirement from a fake into a differentiator, and it makes the
"memory" claim in the pitch cash out on a user-visible feature rather than a
seed script. Cost: one endpoint, one UI control, one memory scope key.

---

## 6. Architecture placement

**A new graph, not an extension of `anomaly_scan`.** Anomaly findings are
per-*transaction* events; subscriptions are per-*vendor series* entities with a
lifecycle (active → drifted → stopped). Different grain, different persistence,
different UI. Overloading `anomalies` would muddy a working feature.

```
agents/findesk_agents/graphs/subscription_scan/
  graph.py     fetch → detect_recurrence → detect_drift → score → critic → persist
  recurrence.py  drift.py  scoring.py  critic.py  state.py
```

- **Critic seat**: pure invariants — every scored row has ≥3 occurrences; no row
  is both `stopped` and `at_risk`; annualized figures reconcile with cadence ×
  amount. Same posture as `cash_forecast/critic.py`: raise on violation, since a
  violation means the engine is broken.
- **Conditional edge** (real, in the N5 sense): `detect_recurrence → {detect_drift
  | nothing_recurring}` — a book with no recurring vendors should not run drift
  and scoring to produce an empty table.
- **Persistence**: `subscriptions` table (unique `tenant_id + vendor_slug`,
  cadence, amount, score components as JSON evidence, status, `usage_confirmed_at`)
  + one Alembic migration + `contracts/db.md`. Model it on `Anomaly` — JSON
  evidence, stable `dedupe_key`, status lifecycle.
- **API**: `GET /subscriptions`, `POST /subscriptions/{id}/usage` (the
  memory-confirmation loop), `POST /subscriptions/{id}/action` → queues an
  approval, executed via the existing token-gated email path. Update
  `contracts/api.yaml` in the same PR (hard rule 1); the surface guard will
  fail CI otherwise.
- **Frontend**: `/subscriptions` — leak score leaderboard, category-wise
  annualized cost, per-row drift evidence with dates, action buttons routing to
  approvals. Model on `/payables` (ranked plan) and `/ims` (evidence rows +
  gated action). **Do not use `StatCard`'s `format` prop for the headline
  numbers** until the `AnimatedNumber` hidden-tab bug is fixed — plain text is
  correct immediately.

Nothing here touches Module B. It is additive.

---

## 7. Seed data — the work item that decides the demo

Design the fixture to exercise every branch, and label each row's purpose so the
demo can narrate it. Target ~12 vendors × 6–8 months ≈ 80–100 debits, extending
the existing `scripts/fixtures/statement_*.csv` format (already `Date, Narration,
Ref No, Debit, Credit, Balance`).

| # | Vendor shape | Proves |
|---|---|---|
| 1 | clean monthly, flat | cadence baseline |
| 2 | monthly, **+12% hike mid-series** | the blind spot the new detector closes |
| 3 | monthly, +50% hike | new detector agrees with the old one |
| 4 | monthly, +₹500 discrete steps | seat creep, not a price hike |
| 5 | quarterly | non-monthly cadence |
| 6 | annual, renewal within 60d | pre-renewal review prompt |
| 7 | monthly, **stopped 3 months ago** | must NOT be flagged (already cancelled) |
| 8 | monthly with one **skipped month** | gap normalization works |
| 9 | usage-based (AWS-like, ±40%) | classified `irregular`, excluded from drift |
| 10 | two vendors, same `category_code` | redundancy signal |
| 11 | duplicate charge in-window | existing detector still fires |
| 12 | rent / payroll — recurring but **not a subscription** | must not be scored as a leak |

Row 12 matters more than it looks: rent and salaries are the largest recurring
debits in any SME book. A leak detector that ranks payroll as your biggest
"subscription leak" is worse than useless, and the live data's largest recurring
debit is WeWork rent. Needs an explicit exclusion (by `category_code`, plus a
user override that persists to memory).

---

## 8. SMS / email ingestion — cheap and credible

PS1 names SMS and email explicitly. FinDesk's email tool *sends*; it does not
parse inbound. The honest cheap version follows the pattern every other FinDesk
connector already uses (`tally`, `ims`, `udyam`): a **fixture-driven
`sms_alerts` tool** that parses common Indian bank debit-alert templates
(HDFC/ICICI/SBI) into the same shape the CSV parser emits, tested against
recorded samples, and listed as **Fixture-tested** in the README integration
table — not "Live."

~1 day, ticks a named focus area, and does not pretend to carrier access.

---

## 9. Effort

**Minimum credible (~5 days)** — a working, honest PS1 submission:

| | Item | Est. |
|---|---|---|
| 1 | `recurrence.py` + vectors | 1.5 d |
| 2 | `drift.py` + vectors | 1 d |
| 3 | `scoring.py` + vectors | 0.5 d |
| 4 | `subscription_scan` graph + migration + persistence | 1 d |
| 5 | **Seed fixture (§7)** | 1 d |
| 6 | `GET /subscriptions` + approval-gated action | 0.5 d |
| 7 | `/subscriptions` page | 1 d |

(Overlaps compress this to ~5 elapsed days; the estimates sum higher because
1–3 are the same sitting.)

**Full (~10 days)** adds: the memory usage-confirmation loop (§5, 0.5 d), the
`sms_alerts` tool (§8, 1 d), category-wise cost visualization beyond a table
(1 d), seat-creep detection (0.5 d), e2e specs + a11y pass (1 d).

**Cut first if time runs out:** SMS tool, seat creep, chart polish. **Never cut:**
the seed fixture (§7) or the stopped-series exclusion (§4.1) — without the first
there is no demo, and without the second the demo actively misleads.

---

## 10. Risks and what not to do

- **Don't lower `OUT_OF_PATTERN_FACTOR`** to catch price creep. It would flood
  the anomaly queue with normal variance and break a working feature. New
  detector, new grain.
- **Don't let the leak score rank rent or payroll.** See §7 row 12.
- **Don't auto-cancel anything**, even behind a confirm dialog. The approval gate
  exists; use it. "Recommend-only" is a selling point, not a limitation.
- **Don't claim "unused" detection** you cannot compute. §5 option 3 or scope it
  out loud.
- **Don't drop Module B from the repo** to look focused. Keep it, mention it as
  depth. It is the reason this codebase reads as serious.
- **Judge risk:** someone may insist PS1 means consumer. Mitigation: lead with
  the reframe and the reason, and have one slide showing the same engine over a
  personal statement — the detectors are entity-agnostic, only the framing and
  the exclusion list differ. That slide is cheap insurance.

---

## 11. Verdict

Aligning with PS1 is **feasible in about a week** and does not require abandoning
what exists — categorization, ingestion, payee normalization, the approval gate,
duplicate detection and the whole trust layer all transfer unchanged.

But it is not the cosmetic job the feature-list overlap suggests. Three things
must genuinely be built: **cadence detection** (absent), **step-change detection**
(the existing detector provably cannot see a 24% price hike), and **demo data
that actually recurs** (currently one repeating vendor). The first two are a
day and a half each of pure, testable functions. The third is the one that
quietly decides whether the demo lands.

The differentiator worth leaning on is not detection — everyone will detect
something. It is that FinDesk **cannot spend your money, shows its evidence with
dates, and remembers what you told it**. PS1's hardest requirement ("unused") is
unanswerable from bank data, and the memory-confirmation loop is a better answer
than the guess every other submission will ship.
