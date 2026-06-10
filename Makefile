.PHONY: up down dev seed lint test test-int contracts smoke logs

# ----- stack -------------------------------------------------------------
up:            ## full dev stack (app + memory). Override ports via docker-compose.override.yml
	docker compose -f docker-compose.yml -f memory/docker-compose.yml $(if $(wildcard docker-compose.override.yml),-f docker-compose.override.yml,) up -d --build

down:
	docker compose -f docker-compose.yml -f memory/docker-compose.yml $(if $(wildcard docker-compose.override.yml),-f docker-compose.override.yml,) down

logs:
	docker compose -f docker-compose.yml -f memory/docker-compose.yml logs -f --tail=100

# ----- dev install -------------------------------------------------------
dev:           ## install all workspaces that exist
	@for ws in backend agents tools memory; do \
	  [ -f $$ws/pyproject.toml ] && (cd $$ws && pip install -e ".[dev]" || pip install -e .) || true; \
	done
	@[ -f frontend/package.json ] && (cd frontend && npm install) || true

PY := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

seed:          ## load synthetic SME fixture data (vendors, clients, 6mo txns, planted anomalies)
	$(PY) scripts/seed_dev_data.py

# ----- quality gates (mirror CI) -----------------------------------------
lint:
	ruff check backend agents tools shared/py || true
	@[ -f frontend/package.json ] && (cd frontend && npm run lint && npx tsc --noEmit) || true

test:          ## unit tests, all workspaces
	@for ws in backend agents tools memory; do \
	  [ -d $$ws/tests/unit ] && (cd $$ws && python -m pytest tests/unit -q) || true; \
	done

test-int:      ## integration tests (testcontainers)
	@for ws in backend agents tools memory; do \
	  [ -d $$ws/tests/integration ] && (cd $$ws && python -m pytest tests/integration -q -m integration) || true; \
	done

contracts:     ## regenerate shared/ from contracts/ (CI fails on drift)
	$(PY) scripts/gen_contracts.py

smoke:         ## weekly end-to-end smoke (docs/team/collaboration.md §4)
	$(PY) scripts/smoke_e2e.py

smoke-memory:  ## memory-service smoke (Recall stack must be up)
	$(PY) scripts/smoke_memory.py
