"""Internal backend API client — the worker's only path to app data."""

from __future__ import annotations

from typing import Any

import httpx

from findesk_agents.config import get_settings


class BackendClient:
    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        settings = get_settings()
        self._client = httpx.AsyncClient(
            base_url=(base_url or settings.backend_base_url).rstrip("/"),
            headers={"X-Internal-Token": token or settings.internal_api_token},
            timeout=30,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def document(self, document_id: str, tenant_id: str) -> dict[str, Any]:
        resp = await self._client.get(
            f"/internal/documents/{document_id}", params={"tenant_id": tenant_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def ingest_transactions(
        self, tenant_id: str, rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/recon/transactions", json={"tenant_id": tenant_id, "rows": rows}
        )
        resp.raise_for_status()
        return resp.json()

    async def recon_context(self, tenant_id: str) -> dict[str, Any]:
        resp = await self._client.get("/internal/recon/context", params={"tenant_id": tenant_id})
        resp.raise_for_status()
        return resp.json()

    async def categorize(
        self, tenant_id: str, run_id: str, items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/recon/categorize",
            json={"tenant_id": tenant_id, "run_id": run_id, "items": items},
        )
        resp.raise_for_status()
        return resp.json()

    async def commit(
        self, tenant_id: str, run_id: str, proposals: list[dict[str, Any]]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/recon/commit",
            json={"tenant_id": tenant_id, "run_id": run_id, "proposals": proposals},
        )
        resp.raise_for_status()
        return resp.json()
