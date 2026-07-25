#!/usr/bin/env bash
# One-command local stack (host-venv recipe — `make up` docker images are
# still broken; see knowledge/sessions/2026-07-15-recall-engine-e2e.md).
#
# Brings up, idempotently:
#   1. app datastores      docker: postgres :15433, redis :6380
#   2. recall datastores   docker: pgvector :15432, neo4j :7687, redis :16379
#   3. embedding shim      host :8090   (model2vec potion-base-8M + dev-echo)
#   4. recall API          host :18000
#   5. backend API         host :8080   (run from repo root — .env is cwd-relative)
#   6. agents worker       host
#   7. seed data           idempotent
#
# Frontend is NOT started here — use your editor's preview (launch.json
# "findesk-frontend") or `cd frontend && npm run dev` (port 3001).
#
# Logs: var/dev/*.log · stop everything: scripts/dev_down.sh

set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
VENV="$ROOT/.venv/bin"
LOGDIR="$ROOT/var/dev"
mkdir -p "$LOGDIR"

up() { # name port command...
  local name="$1" port="$2"; shift 2
  if curl -sf -m 2 -o /dev/null "http://localhost:$port/health" \
     || curl -sf -m 2 -o /dev/null "http://localhost:$port/healthz"; then
    echo "✓ $name already up on :$port"
    return
  fi
  echo "→ starting $name (:$port) — log: var/dev/$name.log"
  nohup "$@" > "$LOGDIR/$name.log" 2>&1 &
  echo $! > "$LOGDIR/$name.pid"
}

wait_health() { # name port [path]
  local name="$1" port="$2" path="${3:-/health}"
  for _ in $(seq 1 60); do
    curl -sf -m 2 -o /dev/null "http://localhost:$port$path" && { echo "✓ $name healthy"; return; }
    sleep 2
  done
  echo "✗ $name did not become healthy on :$port — see var/dev/$name.log" >&2
  exit 1
}

echo "== docker datastores =="
docker compose up -d app-postgres app-redis
(cd memory && docker compose up -d postgres neo4j redis)

echo "== waiting for postgres =="
until docker compose ps app-postgres --format '{{.Status}}' | grep -q healthy; do sleep 2; done
until (cd memory && docker compose ps postgres --format '{{.Status}}' | grep -q healthy); do sleep 2; done

echo "== host services =="
up shim 8090 "$VENV/python" memory/infra/dev/embedding_shim.py
wait_health shim 8090

# recall API must import the `recall` package → run with memory/ as cwd
if ! curl -sf -m 2 -o /dev/null http://localhost:18000/health; then
  echo "→ starting recall (:18000) — log: var/dev/recall.log"
  (cd memory && \
   RECALL_POSTGRES_DSN="postgresql+asyncpg://recall:recall@localhost:15432/recall" \
   RECALL_NEO4J_URI="bolt://localhost:7687" \
   RECALL_REDIS_URL="redis://localhost:16379/0" \
   RECALL_LOCAL_BASE_URL="http://localhost:8090/v1" \
   nohup "$VENV/uvicorn" recall.api.app:app --port 18000 > "$LOGDIR/recall.log" 2>&1 & \
   echo $! > "$LOGDIR/recall.pid")
else
  echo "✓ recall already up on :18000"
fi
wait_health recall 18000

# recall migrations (no-op when at head)
(cd memory && \
 RECALL_POSTGRES_DSN="postgresql+asyncpg://recall:recall@localhost:15432/recall" \
 "$VENV/alembic" upgrade head)

up backend 8080 "$VENV/uvicorn" app.main:app --port 8080
wait_health backend 8080 /healthz

if ! pgrep -f "findesk_agents.worker" > /dev/null; then
  echo "→ starting worker — log: var/dev/worker.log"
  nohup "$VENV/python" -m findesk_agents.worker > "$LOGDIR/worker.log" 2>&1 &
  echo $! > "$LOGDIR/worker.pid"
else
  echo "✓ worker already running"
fi

echo "== seed (idempotent) =="
"$VENV/python" scripts/seed_dev_data.py | tail -2

echo
echo "stack up. login: founder@demo.findesk.in / demo1234"
echo "frontend: cd frontend && npm run dev  (http://localhost:3001)"
