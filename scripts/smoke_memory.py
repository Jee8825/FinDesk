#!/usr/bin/env python3
"""Memory-service smoke: ingest one finance claim, retrieve it back.

Requires the Recall stack up (memory/docker-compose.yml) and a provider key in
memory/.env. Identity mapping per contracts/memory.md.

Usage: .venv/bin/python scripts/smoke_memory.py [base_url]
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("RECALL_BASE_URL", "http://localhost:8000")

CLAIM = "Vendor CloudNINE Solutions invoices are Software Subscription expenses, billed monthly."
SCOPE_KEY = "vendor:smoke-cloudnine"
TENANT = "smoke-tenant"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
        health = await client.get("/health")
        health.raise_for_status()
        print(f"memory service ok at {BASE}")

        ingest = await client.post(
            "/memory/ingest",
            json={
                "user_id": SCOPE_KEY,
                "session_id": "seed:smoke",
                "content": CLAIM,
                "tenant_id": TENANT,
            },
        )
        ingest.raise_for_status()
        units = ingest.json().get("units", [])
        print(f"ingested {len(units)} unit(s)")

        retrieve = await client.post(
            "/memory/retrieve",
            json={
                "user_id": SCOPE_KEY,
                "query": "how do we categorize CloudNINE invoices?",
                "token_budget": 400,
                "tenant_id": TENANT,
            },
        )
        retrieve.raise_for_status()
        memories = retrieve.json().get("memories", [])
        print(f"retrieved {len(memories)} memorie(s):")
        for m in memories:
            print(f"  [{m.get('score', 0):.3f}] {m.get('content', '')[:90]}")
        return 0 if memories else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
