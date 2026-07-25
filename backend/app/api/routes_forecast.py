"""B3 forecast API — latest versioned run with scenario lines."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import Auth
from app.db import session_scope
from app.db.models import Forecast, ForecastLine
from app.services.whatif import apply_whatif, clamp_params

router = APIRouter(tags=["cash"])


class ForecastOut(BaseModel):
    forecast_id: str
    generated_at: str
    horizon_weeks: int
    opening_balance_paise: int
    weekly_outflow_paise: int
    outflow_basis: list[dict[str, Any]]
    gap: dict[str, Any] | None
    narrative: list[str]
    scenarios: dict[str, list[dict[str, Any]]]


@router.get("/forecast", response_model=ForecastOut)
async def latest_forecast(auth: Auth) -> ForecastOut:
    async with session_scope() as session:
        forecast = await session.scalar(
            select(Forecast)
            .where(Forecast.tenant_id == auth.tenant_id)
            .order_by(Forecast.created_at.desc())
            .limit(1)
        )
        if forecast is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no forecast yet — run cash_forecast")
        lines = await session.scalars(
            select(ForecastLine)
            .where(ForecastLine.forecast_id == forecast.id)
            .order_by(ForecastLine.week)
        )
        scenarios: dict[str, list[dict[str, Any]]] = {}
        for line in lines:
            scenarios.setdefault(line.scenario, []).append(
                {
                    "week": line.week,
                    "week_start": line.week_start,
                    "inflow_paise": line.inflow_paise,
                    "outflow_paise": line.outflow_paise,
                    "closing_paise": line.closing_paise,
                    "drivers": line.drivers,
                }
            )
        return ForecastOut(
            forecast_id=forecast.id,
            generated_at=forecast.created_at.isoformat(),
            horizon_weeks=forecast.horizon_weeks,
            opening_balance_paise=forecast.opening_balance_paise,
            weekly_outflow_paise=forecast.weekly_outflow_paise,
            outflow_basis=forecast.outflow_basis,
            gap=forecast.gap,
            narrative=forecast.narrative,
            scenarios=scenarios,
        )


class WhatifIn(BaseModel):
    collection_delay_days: int = Field(default=0, ge=-30, le=60)
    inflow_haircut_bps: int = Field(default=0, ge=0, le=5000)
    extra_monthly_outflow_paise: int = Field(default=0, ge=0, le=10_000_000_000)


class WhatifOut(BaseModel):
    forecast_id: str
    params: dict[str, int]
    weeks: list[dict[str, Any]]
    gap: dict[str, Any] | None
    pushed_out_paise: int
    end_delta_paise: int


@router.post("/forecast/whatif", response_model=WhatifOut)
async def forecast_whatif(auth: Auth, body: WhatifIn) -> WhatifOut:
    """Deterministic sandbox over the stored base scenario — server-side
    money math (the UI only renders). Reads the latest forecast; writes
    nothing."""
    async with session_scope() as session:
        forecast = await session.scalar(
            select(Forecast)
            .where(Forecast.tenant_id == auth.tenant_id)
            .order_by(Forecast.created_at.desc())
            .limit(1)
        )
        if forecast is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no forecast yet — run cash_forecast")
        lines = await session.scalars(
            select(ForecastLine)
            .where(
                ForecastLine.forecast_id == forecast.id,
                ForecastLine.scenario == "base",
            )
            .order_by(ForecastLine.week)
        )
        base_weeks = [
            {
                "week": line.week,
                "week_start": line.week_start,
                "inflow_paise": line.inflow_paise,
                "outflow_paise": line.outflow_paise,
                "closing_paise": line.closing_paise,
            }
            for line in lines
        ]
    params = clamp_params(body.model_dump())
    result = apply_whatif(base_weeks, forecast.opening_balance_paise, params)
    return WhatifOut(
        forecast_id=forecast.id,
        params=dict(params),
        weeks=result["weeks"],
        gap=result["gap"],
        pushed_out_paise=result["pushed_out_paise"],
        end_delta_paise=result["end_delta_paise"],
    )
