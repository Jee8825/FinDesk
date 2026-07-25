"""TReDS tool tests — quote math + the physical listing gate."""

import pytest

from findesk_tools.treds import ListingRefused, SandboxTredsProvider


def test_quote_math_is_tenor_proportional():
    p = SandboxTredsProvider()
    q = p.quote(invoice_ref="INV-1", amount_paise=40_000_000, tenor_days=38)
    # cost = amount × rate × tenor/365 at the provider's annualized rate
    assert q.cost_paise == round(40_000_000 * p.rate_bps / 10_000 * 38 / 365)
    assert q.discount_rate_bps_annual == p.rate_bps
    assert q.unlock_paise == 40_000_000 - q.cost_paise
    shorter = p.quote(invoice_ref="INV-1", amount_paise=40_000_000, tenor_days=10)
    assert shorter.cost_paise < q.cost_paise


def test_quote_rate_is_configurable_per_deployment():
    p = SandboxTredsProvider(rate_bps=1200)
    q = p.quote(invoice_ref="INV-1", amount_paise=40_000_000, tenor_days=38)
    assert q.discount_rate_bps_annual == 1200
    assert q.cost_paise == round(40_000_000 * 0.12 * 38 / 365)


def test_listing_refused_without_token(tmp_path):
    p = SandboxTredsProvider(str(tmp_path))
    q = p.quote(invoice_ref="INV-1", amount_paise=40_000_000, tenor_days=38)
    with pytest.raises(ListingRefused):
        p.list_invoice(tenant_id="t1", quote=q, approval_token=None)
    assert list(tmp_path.rglob("*.json")) == []


def test_listing_with_token_writes_record(tmp_path):
    p = SandboxTredsProvider(str(tmp_path))
    q = p.quote(invoice_ref="INV-1", amount_paise=40_000_000, tenor_days=38)
    receipt = p.list_invoice(tenant_id="t1", quote=q, approval_token="tok-9")
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    assert "tok-9" in files[0].read_text()
    assert receipt.unlock_paise == q.unlock_paise
