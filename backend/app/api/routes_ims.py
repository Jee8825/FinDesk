"""GST IMS queue API — sync, triage queue, gated accept/reject requests.

The route layer never flips a record's state: POST …/action queues a
maker–checker approval; execution happens inside decide_approval with the
minted token (services/approvals.py), mirroring email and TReDS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import Auth
from app.config import get_settings
from app.db import session_scope
from app.db.models import ImsRecord
from app.services.approvals import queue_approval
from app.services.ims import CA_NOTE, get_provider, list_queue, queue_totals, sync_and_match

router = APIRouter(tags=["ims"])


class ImsSyncOut(BaseModel):
    period: str
    pulled: int
    created: int
    refreshed: int
    skipped_decided: int
    recommended_accept: int
    needs_review: int


@router.post("/ims/sync", response_model=ImsSyncOut)
async def sync(auth: Auth, period: str | None = None) -> ImsSyncOut:
    if auth.role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "viewers cannot sync")
    eff_period = period or datetime.now(UTC).strftime("%Y-%m")
    provider = get_provider(get_settings())
    async with session_scope() as session:
        result = await sync_and_match(
            session,
            tenant_id=auth.tenant_id,
            period=eff_period,
            provider=provider,
            actor={"kind": "user", "id": auth.user_id},
        )
    return ImsSyncOut(period=eff_period, **result)


class ImsRecordOut(BaseModel):
    id: str
    supplier_gstin: str
    supplier_name: str
    doc_type: str
    doc_number: str
    doc_date: str
    period: str
    taxable_value_paise: int
    tax_paise: int
    total_paise: int
    state: str
    match_tier: str | None
    matched_bill_number: str | None
    recommendation: str | None
    note: str | None


class ImsQueueOut(BaseModel):
    records: list[ImsRecordOut]
    totals: dict[str, int]
    ca_note: str


def _out(r: ImsRecord) -> ImsRecordOut:
    return ImsRecordOut(
        id=r.id,
        supplier_gstin=r.supplier_gstin,
        supplier_name=r.supplier_name,
        doc_type=r.doc_type,
        doc_number=r.doc_number,
        doc_date=r.doc_date.date().isoformat(),
        period=r.period,
        taxable_value_paise=r.taxable_value_paise,
        tax_paise=r.tax_paise,
        total_paise=r.total_paise,
        state=r.state,
        match_tier=r.match_tier,
        matched_bill_number=r.matched_bill_number,
        recommendation=r.recommendation,
        note=r.note,
    )


@router.get("/ims/queue", response_model=ImsQueueOut)
async def queue(auth: Auth) -> ImsQueueOut:
    async with session_scope() as session:
        rows = await list_queue(session, tenant_id=auth.tenant_id)
        return ImsQueueOut(
            records=[_out(r) for r in rows],
            totals=queue_totals(rows),
            ca_note=CA_NOTE,
        )


class ImsActionRequest(BaseModel):
    target_state: str = Field(pattern="^(accepted|rejected)$")


REQUESTER_ROLES = {"owner", "accountant", "ca"}


@router.post("/ims/records/{record_id}/action")
async def request_action(
    record_id: str, body: ImsActionRequest, auth: Auth
) -> dict[str, Any]:
    if auth.role not in REQUESTER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot request IMS actions")
    async with session_scope() as session:
        row = await session.scalar(
            select(ImsRecord).where(
                ImsRecord.id == record_id, ImsRecord.tenant_id == auth.tenant_id
            )
        )
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "record not found")
        if row.state != "pending":
            raise HTTPException(status.HTTP_409_CONFLICT, f"already {row.state}")
        approval = await queue_approval(
            session,
            tenant_id=auth.tenant_id,
            action_kind="ims_set_state",
            action_payload={
                "ims_record_id": row.id,
                "record_key": row.record_key,
                "doc_number": row.doc_number,
                "supplier_name": row.supplier_name,
                "target_state": body.target_state,
                "tax_paise": row.tax_paise,
                "total_paise": row.total_paise,
            },
            requested_by={"kind": "user", "id": auth.user_id},
            policy_verdicts={
                "recommendation": row.recommendation,
                "match_tier": row.match_tier,
                "against_recommendation": (
                    body.target_state == "rejected"
                    and row.recommendation == "accept"
                )
                or (body.target_state == "accepted" and row.recommendation == "review"),
            },
        )
        return {"ok": True, "approval_id": approval.id}
