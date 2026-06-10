"""Prompt template loader.

All LLM prompts live as files under the top-level ``/prompts`` directory and are
loaded by name (never hardcoded in engine logic). Templates use ``str.format``
placeholders. Loaded templates are cached per process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


@lru_cache
def load(name: str) -> str:
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def render(name: str, **kwargs: object) -> str:
    return load(name).format(**kwargs)
