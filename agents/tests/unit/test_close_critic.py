"""month_end_close critic — the artifact a human signs must be self-consistent."""

from findesk_agents.graphs.month_end_close.critic import MIN_CHECKS, review


def _check(id_, ok=True, severity="warn"):
    return {"id": id_, "label": id_, "ok": ok, "severity": severity, "value": "v", "href": "/x"}


def _checklist(checks, **over):
    blockers = [c["id"] for c in checks if not c["ok"] and c["severity"] == "block"]
    warnings = [c["id"] for c in checks if not c["ok"] and c["severity"] == "warn"]
    base = {
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "ready": not blockers,
        "audit_head": "abc123",
        "generated_at": "t",
    }
    base.update(over)
    return base


def _eight(**last_over):
    ids = [
        "recon_clean",
        "conflicts_zero",
        "anomalies_dispositioned",
        "payables_shield",
        "msme_no_drift",
        "ims_actioned",
        "forecast_fresh",
    ]
    checks = [_check(i) for i in ids] + [_check("audit_chain", severity="block", **last_over)]
    return checks


def test_clean_checklist_passes():
    assert review(_checklist(_eight())) == []


def test_too_few_checks_rejected():
    checks = _eight()[: MIN_CHECKS - 1]
    assert review(_checklist(checks))


def test_missing_keys_and_bad_severity_flagged():
    checks = _eight()
    del checks[0]["href"]
    checks[1]["severity"] = "fatal"
    problems = review(_checklist(checks))
    assert any("missing" in p for p in problems)
    assert any("unknown severity" in p for p in problems)


def test_summary_cross_check_catches_drifted_reducer():
    checks = _eight()
    checks[2]["ok"] = False  # a real warning…
    checklist = _checklist(checks, warnings=[])  # …the summary forgot
    problems = review(checklist)
    assert any("warnings list" in p for p in problems)


def test_ready_contradicting_blockers_flagged():
    checks = _eight()
    checks[0]["ok"] = False
    checks[0]["severity"] = "block"
    checklist = _checklist(checks, ready=True)  # lie
    assert any("ready flag" in p for p in review(checklist))


def test_audit_head_required_when_chain_ok():
    checklist = _checklist(_eight(), audit_head=None)
    assert any("head hash" in p for p in review(checklist))


def test_duplicate_ids_flagged():
    checks = _eight()
    checks[1]["id"] = checks[0]["id"]
    assert any("duplicate" in p for p in review(_checklist(checks)))
