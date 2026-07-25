---
title: 0001-memory-context-layer
type: note
permalink: findesk/decisions/0001-memory-context-layer
---

# ADR 0001 — Persistent memory & context layer for AI-assisted development

Date: 2026-07-14 · Status: accepted

## Context
Every agent session started cold: re-deriving the architecture, the port
remaps, the contract shapes. We want recall-on-start → capture-during-work →
refresh-on-end, automatic and local-first.

## Decision (per layer, after comparing current options)

| Layer | Chosen | Also weighed | Why |
|---|---|---|---|
| Persistent agent memory | **Basic Memory** 0.22.x (MCP, markdown) | Mem0, Zep, Letta, MemPalace, Cognee | Local-first, plain Markdown in-repo (`knowledge/`), Obsidian-native wikilinks, MCP tools with behavior hints, zero cloud dependency. Mem0/Zep win hosted benchmarks but store memory outside the repo and need API keys — wrong trade for a git-versioned team vault. |
| Code / knowledge graph | **graphify** 0.9.7 (`/graphify` skill) | Microsoft GraphRAG, Potpie, Aider repo-map, SCIP | Already installed, persistent `graphify-out/` with query/path/explain CLI, honest EXTRACTED/INFERRED audit trail, incremental `--update`, Obsidian export. GraphRAG is heavier and corpus-oriented; SCIP is symbols-only. |
| Live external docs | **context7 MCP** | raw web search | Purpose-built, version-pinned library docs; already connected. |
| Working memory | **CLAUDE.md** (root + per-layer) | — | Already the repo convention; added a Memory & Context Protocol section. |

## Mechanics
- Vault: `knowledge/` (this folder) — small wiki-linked notes, seeded from the
  real code; `sessions/` dated logs; ADRs here.
- Basic Memory project `findesk` points at `knowledge/` only (never the repo
  root — keeps node_modules/vendored docs out of the index). Registered via
  project-scoped `.mcp.json`; indexing is live via the MCP server (v0.22 has
  no `sync` verb; `reindex`/`status` for maintenance).
- graphify graph over curated sources only: `backend/app`, `agents/`,
  `frontend/src`, `tools/findesk_tools`, `contracts/`, `knowledge/` —
  excludes `memory/` (vendored), `node_modules`, generated `shared/`.
- Hooks in `.claude/settings.json`: SessionStart injects 00-INDEX + newest
  session log + graph god-nodes (pure file reads, exit 0 always); SessionEnd
  runs `scripts/memory/refresh_context.sh` (cache-aware graphify `--update`,
  guarded, backgrounded kill-switch instead of macOS-missing `timeout`).

## Consequences
- Durable facts live in git next to the code they describe; Obsidian (already
  present: `.obsidian/`) renders the vault directly.
- LLM-heavy steps (full graph rebuilds, community labeling) stay out of hooks
  — on-demand only.
- Secrets never enter the vault or scripts; keys are read from env at runtime.