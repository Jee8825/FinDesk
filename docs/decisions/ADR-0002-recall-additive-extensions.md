# ADR-0002 — Minimal Additive Extensions to Vendored Recall

**Status:** accepted · **Date:** 2026-06-10

## Context

Two FinDesk features hit limits of the vendored Recall surface (ADR-0001
restricts changes to prompts / provider config / extension modules; anything
beyond needs an ADR):

1. **Conflict cards (A4)** need the IDs of both conflicting memories to render
   a two-claim card and execute a one-tap resolution. `ConflictLog` stores
   `memory_a`/`memory_b`, but the public `ConflictDTO` omits them.
2. **Groq as the LLM provider.** Groq is OpenAI-compatible but the engine's
   `local` provider hardcodes `api_key="not-needed"` and shares one
   `RECALL_LOCAL_BASE_URL` between the LLM and the embedder — and Groq serves
   no embedding models, so the embedder must stay on the local dev shim while
   the LLM points elsewhere.

## Decision

Two strictly **additive** changes to the vendored copy (no behavior change
when the new fields/envs are absent):

1. `ConflictDTO` gains optional `memory_a`/`memory_b` UUIDs, mapped in
   `engine.list_conflicts`.
2. The `local` LLM provider reads two optional envs:
   `RECALL_LOCAL_LLM_BASE_URL` (falls back to `RECALL_LOCAL_BASE_URL`) and
   `RECALL_LOCAL_API_KEY` (falls back to `"not-needed"`). The embedder is
   untouched.

Core math (decay/confidence/conflict scoring) remains unmodified.

## Consequences

- Conflict cards read both sides of a conflict through the public API; no
  direct DB access into the memory stores.
- Groq (or any OpenAI-compatible endpoint) can power extraction/resolution by
  env alone: `RECALL_LLM_PROVIDER=local`,
  `RECALL_LOCAL_LLM_BASE_URL=https://api.groq.com/openai/v1`,
  `RECALL_LOCAL_API_KEY=gsk_…` — while embeddings stay on the dev shim.
- Both changes are upstream-friendly (small PRs to the Recall repo later);
  until then they're part of our vendored diff, documented here.
