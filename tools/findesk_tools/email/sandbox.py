"""Sandbox email provider — dev/staging delivery into a local outbox.

Writes RFC-822-ish .eml files under ``<outbox_dir>/<tenant_id>/``. Production
swaps in a real provider behind the same surface (contracts/tools.md email@v1);
the approval-token requirement is identical in every environment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from findesk_shared import uuid7

from findesk_tools.email.schemas import EmailDraft, SendReceipt, SendRefused


class SandboxEmailProvider:
    name = "sandbox"

    def __init__(self, outbox_dir: str = "var/outbox") -> None:
        self._outbox = Path(outbox_dir)

    def send(self, *, tenant_id: str, draft: EmailDraft, approval_token: str | None) -> SendReceipt:
        if not approval_token:
            raise SendRefused()
        message_id = uuid7()
        folder = self._outbox / tenant_id
        folder.mkdir(parents=True, exist_ok=True)
        eml = folder / f"{message_id}.eml"
        eml.write_text(
            "\n".join(
                [
                    f"Message-ID: <{message_id}@findesk.sandbox>",
                    f"Date: {datetime.now(UTC).isoformat()}",
                    f"To: {', '.join(draft.to)}",
                    f"Subject: {draft.subject}",
                    f"X-FinDesk-Approval-Token: {approval_token}",
                    f"X-FinDesk-Thread: {draft.thread_ref or '-'}",
                    "Content-Type: text/markdown; charset=utf-8",
                    "",
                    draft.body_md,
                ]
            ),
            encoding="utf-8",
        )
        return SendReceipt(message_id=message_id, provider=self.name, approval_token=approval_token)
