"""Sandbox IMS provider — fixture-driven records, local action receipts.

Fixture mode replays checked-in records (the same shape a GSP IMS API
returns) so the whole accept/reject loop is exercisable offline. Production
swaps a GSP adapter (Adaequare-class) behind the same surface; the token
gate on set_state is identical.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from findesk_shared import uuid7

from findesk_tools.ims.schemas import ImsActionReceipt, ImsActionRefused, ImsRecord, ImsState

_FIXTURES = Path(__file__).parent / "fixtures"


class SandboxImsProvider:
    name = "sandbox-ims"

    def __init__(
        self,
        actions_dir: str = "var/ims",
        *,
        fixture: str = "ims_records.json",
    ) -> None:
        self._dir = Path(actions_dir)
        self._fixture = _FIXTURES / fixture

    def pull_records(self, *, period: str) -> list[ImsRecord]:
        """All records visible in the IMS queue for the period (and earlier
        unactioned ones — the portal keeps them pending until acted on)."""
        raw = json.loads(self._fixture.read_text(encoding="utf-8"))
        records = [ImsRecord(**r) for r in raw["records"]]
        return [r for r in records if r.period <= period]

    def set_state(
        self,
        *,
        tenant_id: str,
        record_key: str,
        state: ImsState,
        approval_token: str | None,
    ) -> ImsActionReceipt:
        if not approval_token:
            raise ImsActionRefused()
        if state == "pending":
            raise ImsActionRefused()  # pending is the default, never an action
        action_id = uuid7()
        acted_at = datetime.now(UTC).isoformat()
        folder = self._dir / tenant_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{action_id}.json").write_text(
            json.dumps(
                {
                    "action_id": action_id,
                    "record_key": record_key,
                    "state": state,
                    "acted_at": acted_at,
                    "approval_token": approval_token,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return ImsActionReceipt(
            action_id=action_id,
            record_key=record_key,
            state=state,
            acted_at=acted_at,
            approval_token=approval_token,
        )
