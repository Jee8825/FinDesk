"""Close checklist core — pure reducer + deterministic pack markdown."""

from app.services.close import checklist_md, summarize


def _check(id_, ok, severity):
    return {"id": id_, "label": id_, "ok": ok, "severity": severity, "value": "v"}


def test_summarize_splits_blockers_and_warnings():
    checks = [
        _check("recon_clean", True, "block"),
        _check("audit_chain", False, "block"),
        _check("ims_actioned", False, "warn"),
    ]
    s = summarize(checks)
    assert s == {"blockers": ["audit_chain"], "warnings": ["ims_actioned"], "ready": False}


def test_summarize_ready_with_only_warnings():
    checks = [_check("recon_clean", True, "block"), _check("forecast_fresh", False, "warn")]
    s = summarize(checks)
    assert s["ready"] is True
    assert s["warnings"] == ["forecast_fresh"]


def test_checklist_md_is_deterministic_and_diffable():
    checklist = {
        "generated_at": "2026-07-23T10:00:00+00:00",
        "audit_head": "abc123",
        "checks": [
            _check("recon_clean", True, "block"),
            _check("ims_actioned", False, "warn"),
        ],
        **summarize(
            [_check("recon_clean", True, "block"), _check("ims_actioned", False, "warn")]
        ),
    }
    md = checklist_md("2026-07", checklist)
    assert md == checklist_md("2026-07", checklist)  # deterministic
    assert "# Month-end close — 2026-07" in md
    assert "- [x] recon_clean" in md
    assert "- [ ] ims_actioned — v **(warn)**" in md
    assert "READY TO SIGN OFF" in md
    assert "`abc123`" in md


def test_checklist_md_blocked_names_blockers():
    checks = [_check("audit_chain", False, "block")]
    checklist = {
        "generated_at": "t",
        "audit_head": None,
        "checks": checks,
        **summarize(checks),
    }
    assert "BLOCKED: audit_chain" in checklist_md("2026-07", checklist)
