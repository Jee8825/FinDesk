"""Token counting for the retrieval budget-packer.

Uses ``tiktoken`` with a model-agnostic encoding. Exact token counts vary across
model families, but the packer only needs a consistent, monotonic estimate.
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache
def _encoder():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text))
