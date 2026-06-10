"""Async HTTP client for the Recall API.

Mirrors the REST surface with typed methods and retry/backoff. Usable directly
or as the transport under the framework adapters.

    async with Recall("http://localhost:8000") as recall:
        await recall.ingest(user_id="u1", session_id="s1", content="...")
        ctx = await recall.retrieve(user_id="u1", query="deployment", token_budget=800)
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from recall.core.types import (
    ConflictDTO,
    IngestResult,
    MemoryUnitDTO,
    RetrieveResult,
    Scope,
    WhyResult,
)

_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.4, min=0.4, max=5),
    reraise=True,
)


class Recall:
    def __init__(self, base_url: str = "http://localhost:8000", *, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def __aenter__(self) -> Recall:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    @_RETRY
    async def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        resp = await self._client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()

    @_RETRY
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def ingest(
        self,
        *,
        user_id: str,
        session_id: str,
        content: str,
        scope: Scope = "private",
        team_id: str | None = None,
        tenant_id: str = "default",
    ) -> IngestResult:
        data = await self._post(
            "/memory/ingest",
            {
                "user_id": user_id,
                "session_id": session_id,
                "content": content,
                "scope": scope,
                "team_id": team_id,
                "tenant_id": tenant_id,
            },
        )
        return IngestResult.model_validate(data)

    async def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        token_budget: int = 2000,
        scope: Scope | None = None,
        team_id: str | None = None,
        session_id: str | None = None,
        tenant_id: str = "default",
    ) -> RetrieveResult:
        data = await self._post(
            "/memory/retrieve",
            {
                "user_id": user_id,
                "query": query,
                "token_budget": token_budget,
                "scope": scope,
                "team_id": team_id,
                "session_id": session_id,
                "tenant_id": tenant_id,
            },
        )
        return RetrieveResult.model_validate(data)

    async def why(self, memory_id: uuid.UUID | str) -> WhyResult:
        return WhyResult.model_validate(await self._get(f"/memory/{memory_id}/why"))

    async def promote(
        self, memory_id: uuid.UUID | str, scope: Scope, team_id: str | None = None
    ) -> None:
        await self._post(
            "/memory/promote",
            {"memory_id": str(memory_id), "scope": scope, "team_id": team_id},
        )

    async def delete(self, memory_id: uuid.UUID | str, cascade: bool = True) -> dict:
        resp = await self._client.delete(f"/memory/{memory_id}", params={"cascade": cascade})
        resp.raise_for_status()
        return resp.json()

    async def user_owned(self, user_id: str, tenant_id: str = "default") -> list[MemoryUnitDTO]:
        data = await self._get(
            "/memory/user-owned", {"user_id": user_id, "tenant_id": tenant_id}
        )
        return [MemoryUnitDTO.model_validate(d) for d in data]

    async def conflicts(self, user_id: str, tenant_id: str = "default") -> list[ConflictDTO]:
        data = await self._get("/conflicts", {"user_id": user_id, "tenant_id": tenant_id})
        return [ConflictDTO.model_validate(d) for d in data]

    async def stats(self, tenant_id: str = "default") -> dict:
        return await self._get("/stats", {"tenant_id": tenant_id})
