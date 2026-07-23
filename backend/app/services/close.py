"""Month-end close checklist (F2) — evidence-linked composition, no new math.

Every check reads an engine that already exists and already has tests; the
close is the *orchestration* of proof, not a new calculation. Blockers stop
sign-off; warnings ride along with an audited rationale. The sign-off itself
is an audit-chain entry (the chain IS the close record — recomputable and
tamper-evident like everything else in the data room).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.books_repo import BooksRepo
from app.db.models import Anomaly, Forecast, ImsRecord
from app.services.audit import verify_chain, write_audit
from app.services.conflicts import list_open_conflicts
from app.services.payables import gather_items

FORECAST_FRESH_DAYS = 7


def summarize(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure reducer: blockers/warnings/ready from check rows."""
    blockers = [c["id"] for c in checks if not c["ok"] and c["severity"] == "block"]
    warnings = [c["id"] for c in checks if not c["ok"] and c["severity"] == "warn"]
    return {"blockers": blockers, "warnings": warnings, "ready": not blockers}


async def build_checklist(
    session: AsyncSession, *, tenant_id: str, now: datetime, bank_rate_bps: int
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    counts = await BooksRepo(session).transaction_counts(tenant_id)
    unmatched = counts.get("unmatched", 0)
    checks.append(
        {
            "id": "recon_clean",
            "label": "Bank feed reconciled",
            "ok": unmatched == 0,
            "severity": "block",
            "value": f"{unmatched} unmatched",
            "href": "/books",
        }
    )

    open_conflicts = len(await list_open_conflicts(session, tenant_id))
    checks.append(
        {
            "id": "conflicts_zero",
            "label": "Belief vs books conflicts resolved",
            "ok": open_conflicts == 0,
            "severity": "block",
            "value": f"{open_conflicts} open",
            "href": "/conflicts",
        }
    )

    open_anomalies = (
        await session.scalar(
            select(func.count())
            .select_from(Anomaly)
            .where(Anomaly.tenant_id == tenant_id, Anomaly.status == "open")
        )
        or 0
    )
    checks.append(
        {
            "id": "anomalies_dispositioned",
            "label": "Anomalies dispositioned",
            "ok": open_anomalies == 0,
            "severity": "warn",
            "value": f"{open_anomalies} open",
            "href": "/anomalies",
        }
    )

    items, _rows, _amounts, _non_mse, drift = await gather_items(
        session, tenant_id, now, bank_rate_bps=bank_rate_bps
    )
    breached = sum(1 for i in items if i["clock"]["band"] == "breached")
    checks.append(
        {
            "id": "payables_shield",
            "label": "§15 clocks unbreached (43B(h))",
            "ok": breached == 0,
            "severity": "warn",
            "value": f"{breached} breached",
            "href": "/payables",
        }
    )
    checks.append(
        {
            "id": "msme_no_drift",
            "label": "Vendor MSME status verified, no drift",
            "ok": len(drift) == 0,
            "severity": "warn",
            "value": f"{len(drift)} drift alert(s)",
            "href": "/payables",
        }
    )

    ims_pending = (
        await session.scalar(
            select(func.count())
            .select_from(ImsRecord)
            .where(ImsRecord.tenant_id == tenant_id, ImsRecord.state == "pending")
        )
        or 0
    )
    checks.append(
        {
            "id": "ims_actioned",
            "label": "IMS queue actioned (ITC decided)",
            "ok": ims_pending == 0,
            "severity": "warn",
            "value": f"{ims_pending} pending",
            "href": "/ims",
        }
    )

    latest = await session.scalar(
        select(Forecast)
        .where(Forecast.tenant_id == tenant_id)
        .order_by(Forecast.created_at.desc())
        .limit(1)
    )
    fresh = bool(
        latest and latest.created_at > now - timedelta(days=FORECAST_FRESH_DAYS)
    )
    checks.append(
        {
            "id": "forecast_fresh",
            "label": f"Forecast recomputed (≤{FORECAST_FRESH_DAYS}d)",
            "ok": fresh,
            "severity": "warn",
            "value": latest.created_at.date().isoformat() if latest else "never",
            "href": "/forecast",
        }
    )

    chain = await verify_chain(session, tenant_id)
    checks.append(
        {
            "id": "audit_chain",
            "label": "Audit chain verifies",
            "ok": bool(chain.get("valid")),
            "severity": "block",
            "value": f"{chain.get('entries', 0)} entries",
            "href": "/dataroom",
        }
    )

    return {
        "generated_at": now.isoformat(),
        "checks": checks,
        **summarize(checks),
        "audit_head": chain.get("head_hash"),
    }


def checklist_md(period: str, checklist: dict[str, Any]) -> str:
    """close_checklist.md for the pack — deterministic, diffable."""
    lines = [
        f"# Month-end close — {period}",
        "",
        f"Generated {checklist['generated_at']} · audit head `{checklist.get('audit_head')}`",
        "",
    ]
    for c in checklist["checks"]:
        mark = "x" if c["ok"] else " "
        sev = "" if c["ok"] else f" **({c['severity']})**"
        lines.append(f"- [{mark}] {c['label']} — {c['value']}{sev}")
    lines += [
        "",
        (
            "READY TO SIGN OFF"
            if checklist["ready"]
            else f"BLOCKED: {', '.join(checklist['blockers'])}"
        ),
        "",
    ]
    return "\n".join(lines)


async def sign_off(
    session: AsyncSession,
    *,
    tenant_id: str,
    period: str,
    checklist: dict[str, Any],
    decider_id: str,
    rationale: str | None,
) -> dict[str, Any]:
    """The close record is an audit entry — recomputable, tamper-evident."""
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor={"kind": "user", "id": decider_id},
        action="close.signoff",
        entity_ref=f"close:{period}",
        payload={
            "period": period,
            "ready": checklist["ready"],
            "warnings": checklist["warnings"],
            "rationale": rationale,
            "audit_head": checklist.get("audit_head"),
            "checks": [
                {"id": c["id"], "ok": c["ok"], "value": c["value"]}
                for c in checklist["checks"]
            ],
        },
    )
    return {"ok": True, "period": period, "warnings": checklist["warnings"]}
