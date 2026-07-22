#!/usr/bin/env bash
# Stop everything scripts/dev_up.sh started (host processes + docker).
set -uo pipefail
cd "$(dirname "$0")/.."

for port in 8080 18000 8090; do
  pids=$(lsof -tnP -iTCP:$port -sTCP:LISTEN 2>/dev/null || true)
  [ -n "$pids" ] && { echo "stopping :$port"; kill $pids; }
done
pkill -f "findesk_agents.worker" 2>/dev/null && echo "stopping worker"

docker compose stop app-postgres app-redis
(cd memory && docker compose stop postgres neo4j redis)
echo "stack down."
