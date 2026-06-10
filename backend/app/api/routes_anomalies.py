"""Anomaly cards API — found money and pattern breaks, human-decided."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import Auth
from app.db import session_scope
from app.db.models import Anomaly
from app.services.audit import write_audit

router = APIRouter(tags=["anomalies"])

DECIDER_ROLES = {"owner", "accountant", "ca"}
DECISIONS = {"accepted", "dismissed", "recovered"}


class AnomalyOut(BaseModel):
    id: str
    kind: str
    severity: str
    vendor_label: str
    evidence: dict[str, Any]
    recommended_action: str
    recoverable_paise: int | None
    status: str
    created_at: str


class DecideRequest(BaseModel):
    decision: str = Field(pattern="^(accepted|dismissed|recovered)$")


@router.get("/anomalies", response_model=list[AnomalyOut])
async def list_anomalies(auth: Auth, status_filter: str | None = "open") -> list[AnomalyOut]:
    async with session_scope() as session:
        q = select(Anomaly).where(Anomaly.tenant_id == auth.tenant_id)
        if status_filter:
            q = q.where(Anomaly.status == status_filter)
        rows = await session.scalars(q.order_by(Anomaly.created_at.desc()).limit(200))
        return [
            AnomalyOut(
                id=a.id,
                kind=a.kind,
                severity=a.severity,
                vendor_label=a.vendor_label,
                evidence=a.evidence,
                recommended_action=a.recommended_action,
                recoverable_paise=a.recoverable_paise,
                status=a.status,
                created_at=a.created_at.isoformat(),
            )
            for a in rows
        ]


@router.post("/anomalies/{anomaly_id}/decide")
async def decide(anomaly_id: str, body: DecideRequest, auth: Auth) -> dict[str, Any]:
    if auth.role not in DECIDER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot decide anomalies")
    async with session_scope() as session:
        anomaly = await session.scalar(
            select(Anomaly).where(Anomaly.id == anomaly_id, Anomaly.tenant_id == auth.tenant_id)
        )
        if anomaly is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "anomaly not found")
        if anomaly.status != "open":
            raise HTTPException(status.HTTP_409_CONFLICT, f"already {anomaly.status}")
        anomaly.status = body.decision
        anomaly.decided_by = auth.user_id
        await write_audit(
            session,
            tenant_id=auth.tenant_id,
            actor={"kind": "user", "id": auth.user_id},
            action=f"anomaly.{body.decision}",
            entity_ref=f"anomaly:{anomaly.id}",
            payload={
                "kind": anomaly.kind,
                "recoverable_paise": anomaly.recoverable_paise,
                "vendor": anomaly.vendor_label,
            },
        )
    return {"ok": True, "status": body.decision}
