"""Recall FastAPI application.

The lifespan handler initializes the Neo4j provenance constraints and disposes of
all datastore connections on shutdown. Routers are mounted per concern.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from recall.config import get_settings
from recall.db import close_driver, close_redis, dispose_engine, init_schema
from recall.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("recall.startup", env=settings.env, llm_provider=settings.llm_provider)
    try:
        await init_schema()
    except Exception as exc:  # noqa: BLE001 - don't crash if Neo4j is briefly unavailable
        log.warning("neo4j.init_schema_failed", error=str(exc))
    yield
    await dispose_engine()
    await close_driver()
    await close_redis()
    log.info("recall.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Recall",
        version="0.2.0",
        description="A living memory engine for LLM agents.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from recall.api.routes_health import router as health_router
    from recall.api.routes_memory import router as memory_router

    app.include_router(health_router)
    app.include_router(memory_router)
    return app


app = create_app()
