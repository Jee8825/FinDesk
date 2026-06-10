"""B3 forecast API — latest versioned run with scenario lines."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import Auth
from app.db import session_scope
from app.db.models import Forecast, ForecastLine

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
