"""TReDS tool tests — quote math + the physical listing gate."""

import pytest

from findesk_tools.treds import ListingRefused, SandboxTredsProvider


def test_quote_math_is_tenor_proportional():
    p = SandboxTredsProvider()
    q = p.quote(invoice_ref="INV-1", amount_paise=40_000_000, tenor_days=38)
    # 4,00,000 × 18% × 38/365 = ₹7,495.89 → 749,589 paise
    assert q.cost_paise == round(40_000_000 * 0.18 * 38 / 365)
    assert q.unlock_paise == 40_000_000 - q.cost_paise
    shorter = p.quote(invoice_ref="INV-1", amount_paise=40_000_000, tenor_days=10)
    assert shorter.cost_paise < q.cost_paise


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
