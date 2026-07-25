"""Credit-pack export — the data room as files a lender can open.

Pure builders (dicts in, text out) + one zip assembler. Deterministic: the
same inputs produce byte-identical files, so a pack can be re-generated and
diffed against what a lender was sent. NO LLM TOUCHES THIS MODULE — a credit
submission is no place for generated prose.
"""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any


def summary_md(room: dict[str, Any]) -> str:
    score = room["findesk_score"]
    chain = room["audit_chain"]
    ev = room["evidence"]
    lines = [
        "# FinDesk Credit Pack",
        "",
        f"Generated: {room['generated_at']}",
        "",
        f"## FinDesk Score: {score['score']}/100",
        "",
        "| Component | Weight | Ratio | Points |",
        "|---|---|---|---|",
    ]
    for name, d in score["components"].items():
        lines.append(f"| {name} | {d['weight']} | {d['ratio']:.2f} | {d['points']:.1f} |")
    lines += [
        "",
        "## Audit chain",
        "",
        (
            f"**VERIFIED** — {chain['rows']} entries, head `{chain.get('head_hash', '')[:16]}…`"
            if chain["ok"]
            else f"**BROKEN at entry #{chain['first_break_index']}** — do not rely on figures"
        ),
        "",
        "Every figure in this pack traces to a hash-chained, append-only audit "
        "log. Verification recomputes the chain live (`GET /audit/verify`).",
        "",
        "## Evidence",
        "",
    ]
    for key, value in ev.items():
        lines.append(f"- {key}: {value}")
    lines += ["", f"> {room['methodology_note']}", ""]
    return "\n".join(lines)


def _csv(headers: list[str], rows: list[list[Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue()


def receivables_csv(items: list[dict[str, Any]]) -> str:
    """items = radar-shaped rows: invoice fields + clock snapshot."""
    return _csv(
        ["invoice", "client", "amount_paise", "statutory_due", "overdue_days",
         "accrued_interest_paise", "escalation_state"],
        [
            [
                i["invoice_number"], i["client"], i["amount_paise"],
                i["clock"]["statutory_due_date"][:10], i["clock"]["overdue_days"],
                i["clock"]["accrued_interest_paise"], i["clock"]["escalation_level"],
            ]
            for i in items
        ],
    )


def payables_csv(items: list[dict[str, Any]]) -> str:
    return _csv(
        ["bill", "vendor", "msme_status", "amount_paise", "outstanding_paise",
         "band", "days_left", "overdue_days", "interest_owed_paise",
         "disallowance_risk_paise"],
        [
            [
                i["bill_number"], i["vendor"], i["msme_status"], i["amount_paise"],
                i["outstanding_paise"], i["clock"]["band"], i["clock"]["days_left"],
                i["clock"]["overdue_days"], i["clock"]["interest_owed_paise"],
                i["clock"]["disallowance_risk_paise"],
            ]
            for i in items
        ],
    )


def forecast_csv(weeks: list[dict[str, Any]]) -> str:
    return _csv(
        ["week", "week_start", "scenario", "inflow_paise", "outflow_paise", "closing_paise"],
        [
            [w["week"], w["week_start"], w["scenario"], w["inflow_paise"],
             w["outflow_paise"], w["closing_paise"]]
            for w in weeks
        ],
    )


def build_pack(
    *,
    room: dict[str, Any],
    receivables: list[dict[str, Any]],
    payables: list[dict[str, Any]],
    forecast_weeks: list[dict[str, Any]],
    extra_files: dict[str, str] | None = None,
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("summary.md", summary_md(room))
        zf.writestr("receivables_aging.csv", receivables_csv(receivables))
        zf.writestr("payables_compliance.csv", payables_csv(payables))
        zf.writestr("forecast_weeks.csv", forecast_csv(forecast_weeks))
        for name, text in (extra_files or {}).items():
            zf.writestr(name, text)  # e.g. close_checklist.md (routes_close)
    return buf.getvalue()
