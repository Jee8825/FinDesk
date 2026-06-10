.PHONY: help install dev up down logs migrate revision lint fmt test test-int test-all bench clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

install:  ## install runtime deps
	pip install -e ".[qwen]"

dev:  ## install dev + all provider extras
	pip install -e ".[dev,qwen,openai,anthropic,adapters,observability,bench]"

up:  ## start the full local stack
	docker compose up -d

down:  ## stop the stack
	docker compose down

logs:  ## tail api logs
	docker compose logs -f api

migrate:  ## apply DB migrations
	alembic upgrade head

revision:  ## autogenerate a migration (m="message")
	alembic revision --autogenerate -m "$(m)"

lint:  ## ruff + mypy
	ruff check recall tests benchmarks
	mypy recall

fmt:  ## auto-format and fix
	ruff check --fix recall tests benchmarks
	black recall tests benchmarks

test:  ## unit tests (no external services)
	pytest tests/unit -q

test-int:  ## integration tests (testcontainers: Postgres/Neo4j)
	pytest tests/integration -q -m integration

test-all:  ## everything
	pytest -q

bench:  ## run all benchmarks and emit charts to benchmarks/output/
	python -m benchmarks.run_all

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__ benchmarks/output
