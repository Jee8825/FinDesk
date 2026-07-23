"""FastAPI app factory. No LLM calls in request handlers — ever."""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_agent import router as agent_router
from app.api.routes_anomalies import router as anomalies_router
from app.api.routes_approvals import router as approvals_router
from app.api.routes_books import router as books_router
from app.api.routes_conflicts import router as conflicts_router
from app.api.routes_dataroom import router as dataroom_router
from app.api.routes_forecast import router as forecast_router
from app.api.routes_ims import router as ims_router
from app.api.routes_internal import router as internal_router
from app.api.routes_payables import router as payables_router
from app.api.routes_radar import router as radar_router
from app.api.routes_reports import router as reports_router
from app.api.routes_wc_actions import router as wc_actions_router
from app.api.routes_why import router as why_router
from app.auth.routes import router as auth_router
from app.db import dispose_engine
from app.events.streams import close_redis, consume_run_events


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    consumer = asyncio.create_task(consume_run_events(stop))
    yield
    stop.set()
    consumer.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await consumer
    from app.memoryclient import close_memory_client

    await close_memory_client()
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    from app.config import assert_safe_settings

    assert_safe_settings()  # refuse to boot non-dev with dev secrets

    app = FastAPI(title="FinDesk API", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(Exception)
    async def unhandled(request, exc):  # noqa: ANN001 — FastAPI signature
        """Structured 500s: clients get a reference id, logs get the traceback."""
        import logging

        from fastapi.responses import JSONResponse
        from findesk_shared import uuid7

        ref = uuid7()
        logging.getLogger("findesk.errors").exception(
            "unhandled error ref=%s path=%s", ref, request.url.path
        )
        return JSONResponse(status_code=500, content={"detail": "internal error", "ref": ref})

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(agent_router, prefix=prefix)
    app.include_router(books_router, prefix=prefix)
    app.include_router(approvals_router, prefix=prefix)
    app.include_router(conflicts_router, prefix=prefix)
    app.include_router(anomalies_router, prefix=prefix)
    app.include_router(reports_router, prefix=prefix)
    app.include_router(radar_router, prefix=prefix)
    app.include_router(payables_router, prefix=prefix)
    app.include_router(forecast_router, prefix=prefix)
    app.include_router(ims_router, prefix=prefix)
    app.include_router(wc_actions_router, prefix=prefix)
    app.include_router(dataroom_router, prefix=prefix)
    app.include_router(why_router, prefix=prefix)
    app.include_router(internal_router)  # worker-only, shared-token auth
    return app


app = create_app()
