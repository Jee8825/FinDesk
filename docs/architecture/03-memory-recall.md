# 03 — Memory Layer (Recall, vendored)

**Owner:** Memory & Context · **Code:** `memory/` · **Contracts:** `contracts/memory.md`

FinDesk's intelligence is memory-driven: pattern crystallization, conflict
detection, decay, confidence accumulation, and provenance all come from
**Recall**, a living-memory engine vendored into this repo at `memory/`.

> **Vendoring policy:** `memory/` is a *copy* of the upstream Recall repo
> (`/Users/Jee/Hackathon/Recall`, Apache-2.0). Upstream is never modified from
> here. FinDesk-specific changes are allowed only in the extension surface
> below; changes to core math (decay/confidence/conflict scoring) require an
> ADR in `docs/decisions/`.

## 1. What Recall provides out of the box

- **Three tiers:** episodic (raw events, short TTL) → semantic (durable facts)
  → procedural (crystallized workflows). Promotion via consolidation passes.
- **Strength axis (decay):** `S(t) = S₀·e^(−λt)`, reinforced on every
  retrieval, tombstoned below threshold → recent behavior outweighs stale
  history with zero manual cleanup.
- **Confidence axis (epistemic):** corroboration raises (diminishing returns),
  contradiction lowers, dormancy drifts down, **crystallization ≥ 0.95** locks
  settled knowledge (stops the agent second-guessing a vendor's category).
- **Write-time conflict detection** with resolution history.
- **Provenance graph (Neo4j):** every belief → its evidence chain (sessions,
  documents, resolutions). GDPR-style atomic deletion included.
- **Budget-packed retrieval:** relevance × recency × strength under an
  explicit token budget.
- Service surface: FastAPI (`/memory/ingest`, `/memory/retrieve`, why-chains),
  async Python SDK (`recall.sdk.Recall`), adapter base with
  `remember()/recall()`.

## 2. How FinDesk maps onto it

| FinDesk concept | Recall mechanism |
|---|---|
| Vendor category history (A3) | semantic units + Bayesian confidence + crystallization |
| TDS/deduction patterns per client (A2) | semantic units, reinforced each reconciliation |
| Book-integrity conflict cards (A4) | write-time conflict detection + resolution log |
| Per-vendor behavioral baselines (A6) | semantic distributions + decay (recent ≫ ancient) |
| Relationship tone for chasing (A7) | semantic + episodic interaction history |
| "Why?" button / credit room (A8/B5) | provenance graph rendered as evidence trail |
| Payment behavior + drift detection (B1) | pattern crystallization + contradiction-as-drift |
| Learned close workflows | procedural tier via consolidation |

Identity mapping: Recall `tenant_id` = FinDesk company; `user_id` =
counterparty scope key (e.g. `vendor:<id>`, `client:<id>`) or acting user for
interaction memory; `session_id` = agent `run_id`. Exact scheme in
`contracts/memory.md`.

## 3. The FinDesk extension surface (what we tweak in the copy)

1. **Prompts** — `memory/prompts/` gets finance-specific extraction and
   consolidation prompts: extract vendor-category claims, deduction-rate
   claims, payment-latency observations, discount-response behavior — instead
   of generic conversational facts.
2. **Typed financial beliefs** — a thin schema layer over the generic memory
   unit (`claim_kind: vendor_category | deduction_pattern | payment_behavior |
   tone_preference | workflow`), carried in unit metadata so retrieval can
   filter by kind.
3. **Conflict export** — Recall's conflict log is polled/streamed by the
   backend and materialized as **conflict cards** in the approval queue; human
   resolutions post back to Recall and the provenance graph.
4. **Why-chain API passthrough** — backend `/api/why/{entity}` composes
   Recall's why-chain with app-DB provenance into one evidence trail for the UI.
5. **Provider config** — heavy/light model wiring per environment.

Everything else in `memory/` is treated as upstream engine code.

## 4. Deployment

Recall runs as its **own service** with its own datastores (Postgres+pgvector,
Neo4j, Redis), composed alongside the app stack (see 09). Agents and backend
talk to it over HTTP via the SDK — never to its databases directly. This keeps
the engine swappable and the upstream merge path open.

## 5. Historical seeding (A1)

Onboarding ingests historical books (chart of accounts, 12–24 months of
categorized entries, client/vendor masters) straight into Tier-2 semantic
memory with moderate confidence, so reconciliation is intelligent from day
one. Seeding scripts live in `memory/scripts/` (FinDesk extension).

## 6. Operational notes

- Provenance writes are best-effort and never block a memory write (upstream
  invariant — keep it).
- Memory calls carry the run/step IDs so Langfuse traces join across services.
- Token budgets for retrieval are set per graph node, not globally.
- Local dev port remaps (machine-specific) go in the gitignored
  `docker-compose.override.yml`.
