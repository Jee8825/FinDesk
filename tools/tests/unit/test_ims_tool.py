"""IMS tool tests — fixture pull shape + the physical set_state gate."""

import pytest

from findesk_tools.ims import ImsActionRefused, SandboxImsProvider


def test_pull_records_parses_fixture_and_sums_exactly():
    p = SandboxImsProvider()
    records = p.pull_records(period="2026-07")
    assert len(records) == 6
    assert all(r.state == "pending" for r in records)
    # paise discipline: taxable + tax == total on every record, no drift
    for r in records:
        assert r.taxable_value_paise + r.tax_paise == r.total_paise
    keys = {r.key for r in records}
    assert len(keys) == 6  # stable identity, no collisions


def test_pull_records_period_filter_keeps_earlier_unactioned():
    p = SandboxImsProvider()
    june = p.pull_records(period="2026-06")
    assert {r.doc_number for r in june} == {"PB-889", "PB-901", "PB-870"}


def test_set_state_refused_without_token(tmp_path):
    p = SandboxImsProvider(str(tmp_path))
    with pytest.raises(ImsActionRefused):
        p.set_state(tenant_id="t1", record_key="k", state="accepted", approval_token=None)
    assert list(tmp_path.rglob("*.json")) == []


def test_set_state_pending_is_never_an_action(tmp_path):
    p = SandboxImsProvider(str(tmp_path))
    with pytest.raises(ImsActionRefused):
        p.set_state(tenant_id="t1", record_key="k", state="pending", approval_token="tok-1")


def test_set_state_with_token_writes_receipt(tmp_path):
    p = SandboxImsProvider(str(tmp_path))
    receipt = p.set_state(
        tenant_id="t1",
        record_key="33AAACS1234F1Z5:invoice:PB-889",
        state="rejected",
        approval_token="tok-7",
    )
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    body = files[0].read_text()
    assert "tok-7" in body and "rejected" in body
    assert receipt.state == "rejected"
    assert receipt.approval_token == "tok-7"
