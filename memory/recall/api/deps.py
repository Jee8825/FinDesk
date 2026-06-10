"""FastAPI dependencies."""

from __future__ import annotations

from recall.core.engine import RecallEngine, get_engine


def engine_dep() -> RecallEngine:
    return get_engine()
