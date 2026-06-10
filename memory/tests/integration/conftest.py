"""Integration fixtures: real Postgres (pgvector) + Neo4j via testcontainers.

These spin up ephemeral containers (random host ports — no conflict with other
local stacks) and point Recall's settings at them. LLM/embedding providers are
faked so the suite needs no API keys; the focus is the storage + engine wiring
(pgvector cosine search, decay reinforcement, Neo4j provenance, conflict log).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def _containers() -> Iterator[None]:
    from testcontainers.neo4j import Neo4jContainer
    from testcontainers.postgres import PostgresContainer

    pg = PostgresContainer(
        "pgvector/pgvector:pg16", username="recall", password="recall", dbname="recall"
    )
    neo = Neo4jContainer("neo4j:5", password="recall-neo4j")
    pg.start()
    neo.start()
    try:
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        os.environ["RECALL_POSTGRES_DSN"] = (
            f"postgresql+asyncpg://recall:recall@{host}:{port}/recall"
        )
        # Neo4jContainer exposes a bolt URL helper.
        bolt = neo.get_connection_url()  # bolt://host:port
        os.environ["RECALL_NEO4J_URI"] = bolt
        os.environ["RECALL_NEO4J_USER"] = "neo4j"
        os.environ["RECALL_NEO4J_PASSWORD"] = "recall-neo4j"

        # Reset cached settings/singletons so they pick up the container env.
        from recall.config import get_settings

        get_settings.cache_clear()
        yield
    finally:
        neo.stop()
        pg.stop()


@pytest_asyncio.fixture
async def schema(_containers: None) -> AsyncIterator[None]:
    """Create the pgvector extension + tables and Neo4j constraints, then drop."""
    from recall.db import close_driver, close_redis, dispose_engine, get_engine, init_schema
    from recall.db.models import Base
    from sqlalchemy import text

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    await init_schema()
    try:
        yield
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        # Dispose all loop-bound singletons so the next (new-loop) test rebuilds
        # them; otherwise asyncpg/neo4j objects leak across event loops.
        await dispose_engine()
        await close_driver()
        await close_redis()
