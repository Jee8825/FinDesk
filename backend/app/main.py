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
from app.api.routes_close import router as close_router
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

    @app.middleware("http")
    async def request_id_middleware(request, call_next):  # noqa: ANN001
        """B3: every request carries an id — accepted from the proxy or
        minted here — echoed on the response and reused as the error ref,
        so frontend↔backend↔worker logs finally join on something."""
        from findesk_shared import uuid7

        rid = request.headers.get("X-Request-ID") or uuid7()
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(Exception)
    async def unhandled(request, exc):  # noqa: ANN001 — FastAPI signature
        """Structured 500s: clients get a reference id, logs get the traceback."""
        import logging

        from fastapi.responses import JSONResponse
        from findesk_shared import uuid7

        ref = getattr(request.state, "request_id", None) or uuid7()
        logging.getLogger("findesk.errors").exception(
            "unhandled error ref=%s path=%s", ref, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "internal error", "ref": ref},
            headers={"X-Request-ID": ref},
        )

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    async def readyz():
        """B2: real readiness — DB and Redis answer, or the probe fails.
        Recall is reported but never gates (graphs degrade without it)."""
        from fastapi.responses import JSONResponse
        from sqlalchemy import text

        from app import memoryclient
        from app.db import get_engine
        from app.events.streams import get_redis

        checks: dict[str, bool] = {}
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["postgres"] = True
        except Exception:  # noqa: BLE001
            checks["postgres"] = False
        try:
            checks["redis"] = bool(await get_redis().ping())
        except Exception:  # noqa: BLE001
            checks["redis"] = False
        checks["recall"] = await memoryclient.ping()  # informational only

        ready = checks["postgres"] and checks["redis"]
        return JSONResponse(status_code=200 if ready else 503, content={"ready": ready, **checks})

    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(agent_router, prefix=prefix)
    app.include_router(books_router, prefix=prefix)
    app.include_router(approvals_router, prefix=prefix)
    app.include_router(conflicts_router, prefix=prefix)
    app.include_router(anomalies_router, prefix=prefix)
    app.include_router(reports_router, prefix=prefix)
    app.include_router(close_router, prefix=prefix)
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
