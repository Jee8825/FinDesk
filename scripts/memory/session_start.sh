#!/bin/bash
# SessionStart hook — inject the knowledge index, the newest session log, and
# the graph's god nodes as context. Pure file reads: no network, no LLM.
# Must NEVER fail the session: every step is guarded, always exits 0.
set +e
ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
[ -z "$ROOT" ] && exit 0

echo "=== FinDesk memory layer — recall snapshot (SessionStart) ==="

if [ -f "$ROOT/knowledge/00-INDEX.md" ]; then
  echo ""
  echo "--- knowledge/00-INDEX.md ---"
  cat "$ROOT/knowledge/00-INDEX.md" 2>/dev/null
fi

LATEST_LOG=$(ls -t "$ROOT"/knowledge/sessions/*.md 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
  echo ""
  echo "--- newest session log: $(basename "$LATEST_LOG") ---"
  cat "$LATEST_LOG" 2>/dev/null
fi

if [ -f "$ROOT/graphify-out/GRAPH_REPORT.md" ]; then
  echo ""
  echo "--- graph god nodes (graphify-out/GRAPH_REPORT.md; query with: graphify query \"...\") ---"
  awk '/^## God Nodes/{flag=1;next}/^## /{flag=0}flag' "$ROOT/graphify-out/GRAPH_REPORT.md" 2>/dev/null | head -15
fi

exit 0
