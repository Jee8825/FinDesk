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

    async def enforcer_context(self, tenant_id: str) -> dict[str, Any]:
        resp = await self._client.get(
            "/internal/enforcer/context", params={"tenant_id": tenant_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def queue_act_letter(
        self, tenant_id: str, run_id: str, letter: dict[str, Any]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/enforcer/act-letter",
            json={"tenant_id": tenant_id, "run_id": run_id, "letter": letter},
        )
        resp.raise_for_status()
        return resp.json()

    async def persist_samadhaan_prep(
        self, tenant_id: str, run_id: str, doc: dict[str, Any]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/enforcer/samadhaan-prep",
            json={"tenant_id": tenant_id, "run_id": run_id, "doc": doc},
        )
        resp.raise_for_status()
        return resp.json()

    async def latest_gap(self, tenant_id: str) -> dict[str, Any] | None:
        resp = await self._client.get(
            "/internal/forecast/latest-gap", params={"tenant_id": tenant_id}
        )
        resp.raise_for_status()
        return resp.json().get("gap")

    async def persist_wc_actions(
        self, tenant_id: str, run_id: str, options: list[dict[str, Any]]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/wc-actions",
            json={"tenant_id": tenant_id, "run_id": run_id, "options": options},
        )
        resp.raise_for_status()
        return resp.json()

    async def forecast_context(self, tenant_id: str) -> dict[str, Any]:
        resp = await self._client.get(
            "/internal/forecast/context", params={"tenant_id": tenant_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def persist_forecast(
        self, tenant_id: str, run_id: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/forecast",
            json={"tenant_id": tenant_id, "run_id": run_id, "result": result},
        )
        resp.raise_for_status()
        return resp.json()

    async def collections_context(self, tenant_id: str) -> dict[str, Any]:
        resp = await self._client.get(
            "/internal/collections/context", params={"tenant_id": tenant_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def queue_email_approvals(
        self, tenant_id: str, run_id: str, drafts: list[dict[str, Any]]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/collections/queue",
            json={"tenant_id": tenant_id, "run_id": run_id, "drafts": drafts},
        )
        resp.raise_for_status()
        return resp.json()

    async def anomaly_context(self, tenant_id: str) -> dict[str, Any]:
        resp = await self._client.get(
            "/internal/anomalies/context", params={"tenant_id": tenant_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def persist_anomalies(
        self, tenant_id: str, run_id: str, findings: list[dict[str, Any]]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/anomalies",
            json={"tenant_id": tenant_id, "run_id": run_id, "findings": findings},
        )
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

    async def leak_context(self, tenant_id: str) -> dict[str, Any]:
        resp = await self._client.get(
            "/internal/leaks/context", params={"tenant_id": tenant_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def persist_leaks(
        self, tenant_id: str, run_id: str, rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/leaks",
            json={"tenant_id": tenant_id, "run_id": run_id, "rows": rows},
        )
        resp.raise_for_status()
        return resp.json()

    async def close_context(self, tenant_id: str) -> dict[str, Any]:
        resp = await self._client.get("/internal/close/context", params={"tenant_id": tenant_id})
        resp.raise_for_status()
        return resp.json()

    async def persist_close_run(
        self, tenant_id: str, run_id: str, *, period: str, checklist: dict[str, Any]
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/internal/close/run",
            json={
                "tenant_id": tenant_id,
                "run_id": run_id,
                "period": period,
                "checklist": checklist,
            },
        )
        resp.raise_for_status()
        return resp.json()
