#!/bin/bash
# SessionEnd hook — refresh the memory index and the code graph.
# Cache-aware and LLM-free: graphify update is deterministic AST re-extraction;
# basic-memory reindex is incremental. macOS has no `timeout`, so long steps
# get a background-PID + sleep kill guard. Never fails the session: exit 0.
set +e
ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
[ -z "$ROOT" ] && exit 0
LOG="$ROOT/graphify-out/.refresh.log"
mkdir -p "$ROOT/graphify-out" 2>/dev/null

run_capped() { # run_capped <seconds> <cmd...>
  local cap="$1"; shift
  ( "$@" ) >>"$LOG" 2>&1 &
  local pid=$!
  ( sleep "$cap" && kill "$pid" 2>/dev/null ) &
  local guard=$!
  wait "$pid" 2>/dev/null
  kill "$guard" 2>/dev/null
  wait "$guard" 2>/dev/null
}

echo "refresh_context $(date '+%Y-%m-%d %H:%M:%S')" >>"$LOG" 2>/dev/null

# 1. Code graph — structural update only (no LLM); 120s cap.
if command -v graphify >/dev/null 2>&1; then
  run_capped 120 graphify update "$ROOT"
fi

# 2. Memory index — incremental reindex of the knowledge/ vault; 90s cap.
#    (basic-memory 0.22 has no `sync` verb; live sync happens in the MCP
#    server, this catches notes edited outside a session.)
if command -v basic-memory >/dev/null 2>&1; then
  run_capped 90 basic-memory reindex --project findesk
fi

# Filter known-noisy multiprocessing stderr out of the log tail we keep.
if [ -f "$LOG" ]; then
  grep -v -e "worker failed" -e "resource_tracker" -e "leaked semaphore" "$LOG" \
    | tail -200 > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null
fi

exit 0
