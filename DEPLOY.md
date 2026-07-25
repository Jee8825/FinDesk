# Deploying LeakRadar / FinDesk

Frontend on **Vercel**, backend plane on **Render**. The frontend proxies
`/api/v1/*` to the API through Next rewrites (`frontend/next.config.mjs`), so
everything is same-origin and there is no CORS configuration anywhere.

```
Vercel (Next.js)  ──rewrite──▶  Render web: findesk-api ──▶ Postgres
                                        │                └─▶ Redis
                                        └── Render worker: findesk-worker
```

## 1. Render (do this first — Vercel needs the API URL)

Dashboard → **New → Blueprint** → select this repo. `render.yaml` provisions
Postgres 16, a Redis key-value store, the API web service and the agents worker.

Then set the secrets Render cannot generate for you:

| Service | Variable | Value |
|---|---|---|
| `findesk-worker` | `INTERNAL_API_TOKEN` | **copy from `findesk-api`** — the two must match |
| `findesk-worker` | `GROQ_API_KEY` | optional, from console.groq.com |
| `findesk-worker` | `OPENROUTER_API_KEY` | optional, from openrouter.ai |
| both | `RECALL_BASE_URL` | leave blank unless you deploy Recall (see §4) |

`INTERNAL_API_TOKEN` is the one that will bite you: Render generates it on the
API service, and a `generateValue` cannot be referenced across services, so the
worker gets its own unless you paste the API's value in. Mismatched tokens mean
every internal call 401s and runs fail with no obvious cause.

Migrations run automatically — `backend/Dockerfile` does `alembic upgrade head`
before starting uvicorn.

### Seed the demo data

Render free instances have no shell, so run it against the external connection
string from your machine, once:

```bash
APP_DATABASE_URL='<Render external connection string>' \
  .venv/bin/python scripts/seed_dev_data.py
```

That creates the demo login, the two LeakRadar tenants (business + personal)
with their fixtures, and the chart of accounts. It is idempotent.

## 2. Vercel

New Project → import the repo → **Root Directory: `frontend`**. The framework
preset and build command come from `frontend/vercel.json`.

One environment variable:

| Variable | Value |
|---|---|
| `BACKEND_URL` | `https://findesk-api.onrender.com` (your API service URL, no trailing slash) |

Redeploy after setting it — `next.config.mjs` reads it at build time.

## 3. Free-tier realities

Worth knowing before a demo, not during one:

- **Render free web services sleep after ~15 minutes idle.** The first request
  then takes ~50 seconds. Hit the API once before you present.
- **The free worker sleeps too.** A sleeping worker means agent runs queue and
  never execute — the run sits at "queued". Wake both, or move the worker to a
  paid instance for anything resembling a pilot.
- **Free Postgres expires after 30 days.** Back up or upgrade before then.
- **SSE through the Vercel proxy** can be cut short by function limits. The
  client already falls back to polling (`useRunStream`), so runs still complete
  and the UI still updates — it just stops being live-streamed.
- **LLM free tiers are day-capped.** With no keys the app still works: vendor
  names fall back to the deterministic slug, and narratives and drafts are
  simply absent. Every number is deterministic either way.

## 3a. Do not scale the API past one instance

`findesk-api` persists agent run steps by consuming the `agents:events` Redis
stream through a single consumer group. A second replica *splits* that stream —
each instance records only the events it happened to receive, and the Run Viewer
shows steps frozen at "started" even though the run succeeded.

Measured, not theorised: two backends against one stream lost 2 of 9 steps on a
`subscription_scan`; a single backend recorded all 9 in order. `numInstances: 1`
is pinned in the blueprint. Scaling out needs a per-replica consumer name first.

## 4. Recall (optional, not in the blueprint)

The memory engine needs Postgres+pgvector, Neo4j and its own Redis. Neo4j has no
managed Render service, so it is left out deliberately rather than half-wired.

Nothing breaks without it. Memory calls no-op, and the LeakRadar
usage-confirmation loop still works end to end because the human's answer is
stored on the `subscriptions` row and served by `/internal/leaks/context` — the
memory engine adds decay and re-asking on top, it is not the system of record.

To add it later: a pgvector Postgres, Neo4j Aura (free tier), a Redis instance,
the Recall API as a web service, and the embedding shim — then set
`RECALL_BASE_URL` on both the API and the worker.

## 5. Verifying a deploy

```bash
curl -s https://<api>.onrender.com/healthz
curl -s https://<api>.onrender.com/readyz
```

Then in the app: log in, open **LeakRadar**, hit **Scan for leaks**, and watch
the run appear under `/runs`. If the run stays `queued`, the worker is asleep or
its `INTERNAL_API_TOKEN` does not match the API's.
