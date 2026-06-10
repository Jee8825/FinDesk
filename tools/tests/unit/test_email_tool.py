"""Email tool tests — the P2 guardrail must be physical."""

import pytest

from findesk_tools.email import EmailDraft, SandboxEmailProvider, SendRefused


def _draft():
    return EmailDraft(
        to=["accounts@client.demo.findesk.in"],
        subject="Payment reminder: INV-42",
        body_md="Dear team,\n\nPlease pay.",
        thread_ref="invoice:i1",
    )


def test_send_refused_without_token(tmp_path):
    provider = SandboxEmailProvider(str(tmp_path))
    with pytest.raises(SendRefused):
        provider.send(tenant_id="t1", draft=_draft(), approval_token=None)
    with pytest.raises(SendRefused):
        provider.send(tenant_id="t1", draft=_draft(), approval_token="")
    assert list(tmp_path.rglob("*.eml")) == []


def test_send_with_token_writes_outbox(tmp_path):
    provider = SandboxEmailProvider(str(tmp_path))
    receipt = provider.send(tenant_id="t1", draft=_draft(), approval_token="tok-123")
    files = list(tmp_path.rglob("*.eml"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "X-FinDesk-Approval-Token: tok-123" in content
    assert "Subject: Payment reminder: INV-42" in content
    assert receipt.provider == "sandbox"
