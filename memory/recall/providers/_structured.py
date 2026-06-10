"""Helpers shared by providers for robust structured (JSON) output.

LLMs do not reliably emit clean JSON. These helpers extract the most likely JSON
payload from a noisy completion and validate it against a Pydantic schema, with
a bounded retry that feeds the parse error back to the model.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> str:
    """Best-effort extraction of a JSON object/array from a model completion."""
    fenced = _FENCE_RE.search(text)
    if fenced:
        return fenced.group(1).strip()
    # Fall back to the first balanced {...} or [...] span.
    start = min(
        (i for i in (text.find("{"), text.find("[")) if i != -1),
        default=-1,
    )
    if start == -1:
        return text.strip()
    return text[start:].strip()


def schema_instructions(schema: type[BaseModel]) -> str:
    """Render a compact instruction telling the model what JSON shape to emit."""
    return (
        "Respond with a single valid JSON value and nothing else. "
        "It must conform to this JSON Schema:\n"
        f"{json.dumps(schema.model_json_schema())}"
    )


async def json_with_retry(
    call: Callable[[str], Awaitable[str]],
    base_prompt: str,
    schema: type[T],
    *,
    max_retries: int = 2,
) -> T:
    """Call ``call(prompt) -> text``, parse into ``schema``, retry on failure.

    On a parse/validation error the error message is appended to the prompt so
    the model can correct itself. Raises the last error if all attempts fail.
    """
    prompt = f"{base_prompt}\n\n{schema_instructions(schema)}"
    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        text = await call(prompt)
        try:
            return schema.model_validate_json(extract_json(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            prompt = (
                f"{base_prompt}\n\n{schema_instructions(schema)}\n\n"
                f"Your previous response failed to parse with error: {exc}\n"
                "Return corrected JSON only."
            )
    assert last_error is not None
    raise last_error
