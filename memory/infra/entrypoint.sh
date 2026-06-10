#!/usr/bin/env bash
# Backend container entrypoint: apply DB migrations, then exec the server.
# Neo4j constraints are created by the app on startup (see api/app.py lifespan).
set -euo pipefail

echo "[entrypoint] running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
