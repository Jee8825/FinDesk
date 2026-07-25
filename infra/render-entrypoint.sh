#!/usr/bin/env bash
# Start the API and the agents worker in one container (see Dockerfile.render).
set -euo pipefail

echo "==> migrations"
cd /srv/backend && alembic upgrade head

echo "==> agents worker"
cd /srv/agents && python -m findesk_agents.worker &
worker=$!

echo "==> api on ${PORT:-8080}"
cd /srv/backend && uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" &
api=$!

# Exit as soon as EITHER dies, so Render restarts the whole container. Without
# this a dead worker leaves a healthy-looking API serving runs that never
# execute — the failure mode hardest to spot from the outside.
wait -n "$worker" "$api"
code=$?
echo "==> a process exited (${code}); stopping the container"
kill "$worker" "$api" 2>/dev/null || true
exit "$code"
