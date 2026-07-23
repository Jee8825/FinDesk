"""Sandbox Udyam verifier — fixture-driven register lookups.

Fixture replays the shape commercial verify APIs (IDfy/AuthBridge/Deepvue
class) return. Production swaps one of those adapters behind the same
surface; there is no token gate because verification never acts on anything.
"""

from __future__ import annotations

import json
from pathlib import Path

from findesk_tools.udyam.schemas import UdyamVerification

_FIXTURES = Path(__file__).parent / "fixtures"


class SandboxUdyamProvider:
    name = "sandbox-udyam"

    def __init__(self, *, fixture: str = "udyam.json") -> None:
        self._fixture = _FIXTURES / fixture

    def verify(self, *, urn: str) -> UdyamVerification:
        register = json.loads(self._fixture.read_text(encoding="utf-8"))["register"]
        entry = register.get(urn.strip().upper())
        if entry is None:
            return UdyamVerification(urn=urn.strip().upper(), found=False)
        return UdyamVerification(urn=urn.strip().upper(), found=True, **entry)
