"""Credit-pack builders — deterministic files, correct rows, zip integrity."""

import io
import zipfile

from app.services.dataroom_export import (
    build_pack,
    forecast_csv,
    payables_csv,
    receivables_csv,
    summary_md,
)

ROOM = {
    "generated_at": "2026-07-23T10:00:00+00:00",
    "findesk_score": {
        "score": 82,
        "components": {
            "reconciliation": {"ratio": 0.95, "weight": 25, "points": 23.8},
            "audit_integrity": {"ratio": 1.0, "weight": 20, "points": 20.0},
        },
    },
    "audit_chain": {"ok": True, "rows": 98, "head_hash": "abc123def456abc123def456"},
    "evidence": {"bank_transactions": 120, "open_receivables_paise": 5_000_000},
    "methodology_note": "weights published; recompute everything",
}

RECEIVABLE = {
    "invoice_number": "INV-1",
    "client": "Acme",
    "amount_paise": 1_000_000,
    "clock": {
        "statutory_due_date": "2026-07-04T00:00:00+00:00",
        "overdue_days": 18,
        "accrued_interest_paise": 9_000,
        "escalation_level": "reminder",
    },
}

PAYABLE = {
    "bill_number": "PB-1",
    "vendor": "Sundaram",
    "msme_status": "micro",
    "amount_paise": 2_000_000,
    "outstanding_paise": 1_500_000,
    "clock": {
        "band": "breached",
        "days_left": 0,
        "overdue_days": 5,
        "interest_owed_paise": 4_000,
        "disallowance_risk_paise": 1_500_000,
    },
}

WEEK = {
    "week": 0, "week_start": "2026-07-20", "scenario": "base",
    "inflow_paise": 100, "outflow_paise": 40, "closing_paise": 60,
}


def test_summary_carries_score_verification_and_head_hash():
    md = summary_md(ROOM)
    assert "82/100" in md
    assert "VERIFIED" in md and "98 entries" in md
    assert "abc123def456abc1" in md  # head hash prefix, verifiable by a lender
    assert "reconciliation | 25 | 0.95" in md


def test_summary_shouts_when_chain_is_broken():
    broken = {**ROOM, "audit_chain": {"ok": False, "rows": 98, "first_break_index": 2}}
    md = summary_md(broken)
    assert "BROKEN at entry #2" in md
    assert "do not rely" in md


def test_csvs_have_headers_and_rows():
    r = receivables_csv([RECEIVABLE]).splitlines()
    assert r[0].startswith("invoice,client,")
    assert r[1] == "INV-1,Acme,1000000,2026-07-04,18,9000,reminder"
    p = payables_csv([PAYABLE]).splitlines()
    assert p[1] == "PB-1,Sundaram,micro,2000000,1500000,breached,0,5,4000,1500000"
    f = forecast_csv([WEEK]).splitlines()
    assert f[1] == "0,2026-07-20,base,100,40,60"


def test_pack_zips_all_four_files_deterministically():
    pack1 = build_pack(
        room=ROOM, receivables=[RECEIVABLE], payables=[PAYABLE], forecast_weeks=[WEEK]
    )
    with zipfile.ZipFile(io.BytesIO(pack1)) as zf:
        assert sorted(zf.namelist()) == [
            "forecast_weeks.csv",
            "payables_compliance.csv",
            "receivables_aging.csv",
            "summary.md",
        ]
        assert "82/100" in zf.read("summary.md").decode()
