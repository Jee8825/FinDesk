# ADR-0003 — Wire Dormant/Corroboration Confidence Dynamics and Tenant-Scope why/delete/promote

**Status:** accepted · **Date:** 2026-06-14

## Context

A correctness audit of the vendored Recall memory layer (`memory/`) found that
several behaviors the contracts already promise were not actually reachable at
runtime, plus one tenancy gap:

1. **Dormancy drift never ran.** `confidence.dormancy_drift` is defined,
   unit-tested, and named in `contracts/memory.md` ("drift on dormancy") and the
   consolidation docstring, but `apply_dormancy_and_crystallize` only
   crystallized — it never drifted. The `last_referenced_session` column that
   would feed it was never read or written.
2. **Corroboration diminishing-returns never accumulated.** `corroboration_count`
   was read to compute the diminishing delta but never written; decisive
   conflict resolutions create a fresh row, so the count reset to 0 every time.
   Net effect: every corroboration added a flat +0.15, contradicting the
   "saturates after ~5 repeats" contract language.
3. **`record_corroboration` provenance edge was dead** — defined, never called.
4. **`why` / `delete` / `promote` were not tenant-scoped.** They took only a
   memory UUID; the engine and repository never filtered by `tenant_id`. This
   violates FinDesk hard rule #6 ("No cross-tenant reads, ever") — any caller
   with a UUID could read another tenant's provenance, delete it, or re-scope it.
5. A retired belief stayed in the in-memory candidate list during a multi-fact
   ingest, so a later fact in the same batch could "conflict" against a
   tombstoned belief.

None of these were caught by tests because the unit tests exercise the pure
math functions in isolation, not the wiring.

## Decision

Wire the already-specified behavior into the live flow; **no decay/confidence/
conflict formula is changed**, so the engine math and benchmark baselines are
untouched. The changes are confined to orchestration, persistence, and the API
edge:

- **Dormancy** — `apply_dormancy_and_crystallize` now applies
  `confidence.dormancy_drift` before the crystallization check, using a new
  repository helper `count_sessions_since` (distinct `source_session_id` of the
  user's units created after the belief's last reference) as the "sessions idle"
  signal. Retrieval now stamps `last_referenced_session`. Consolidation reports a
  new additive `dormant_drifted` count.
- **Corroboration** — decisive resolutions carry `corroboration_count =
  existing + 1` onto the surviving unit (new optional arg on
  `repository.insert_memory`), so diminishing returns actually diminish. The
  surviving belief also records a `record_corroboration` provenance edge.
- **Tenant scoping** — `why` / `delete` / `promote` accept an optional
  `tenant_id` (default `"default"`, backward compatible). `why` authorizes
  against the relational store before exposing the graph; `delete` and
  `update_scope` filter by tenant; cross-tenant `delete` → 404, cross-tenant
  `promote` → 403, cross-tenant `why` → empty chain.
- **Batch hygiene** — `conflict.find_nearest` skips `tombstoned` candidates and
  the engine marks a retired belief tombstoned in memory.

Contract/version: `memory/contracts/api.md` updated (optional `tenant_id` on
why/delete/promote; `dormant_drifted` added to the consolidate response) and the
OpenAPI version bumped `0.1.0 → 0.2.0`. The FinDesk-facing `contracts/memory.md`
needs no change — these fixes bring the implementation *into line* with what it
already states.

## Consequences

- The two advertised confidence dynamics now actually evolve beliefs over time;
  a benchmark that exercises confidence across sessions will now show movement
  (re-baseline if one exists).
- The memory service enforces tenant isolation itself, not only via the backend
  in front of it — defense in depth for hard rule #6. Authentication of the
  caller is still the backend's responsibility; this ADR only closes the
  cross-tenant-by-UUID hole.
- `count_sessions_since` runs once per active semantic unit during
  consolidation (an N-query background pass). Acceptable at current scale; a
  set-based rewrite is the obvious optimization if consolidation gets hot.
- New tests: a pure unit test for the tombstoned-candidate skip, and three
  integration tests (corroboration accumulation, dormancy drift, cross-tenant
  isolation).
