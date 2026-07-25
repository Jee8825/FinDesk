# Deploying LeakRadar / FinDesk — Render + Vercel (free tier)

Backend plane on **Render**, frontend on **Vercel**. The frontend proxies
`/api/v1/*` to the API through Next rewrites (`frontend/next.config.mjs`), so
everything is same-origin and there is no CORS configuration anywhere.

```
Vercel (Next.js)  ──rewrite──▶  Render web service ──▶ Postgres
   BACKEND_URL                  ├─ FastAPI (API)   └─▶ Redis (Key Value)
                                └─ agents worker
                                        ▲
                                UptimeRobot pings /healthz every 5 min
```

## The one free-tier constraint that shapes everything

**Render background workers are a paid service (~$7/mo).** On the free tier a
separate worker cannot exist — and with no worker, every agent run sits at
`queued` forever. That is the whole product, so the free-tier image
(`infra/Dockerfile.render`) runs the API *and* the worker as two processes in
one web service.

This changes nothing architecturally: the worker still talks to the API over the
internal HTTP API exactly as in a split deployment, just over loopback. The
entrypoint exits if **either** process dies, so Render restarts the container
rather than leaving a healthy-looking API serving runs that never execute.

The other number that matters: the free tier gives **750 instance-hours/month**.
An always-on service uses ~730, so **one** service can stay awake round the
clock. Two cannot — another reason the combined image is the right shape here.

---

## 1. Render

### 1.1 Create the services

Dashboard → **New → Blueprint** → connect this repo → apply. `render.yaml`
provisions:

| Resource | Name | Plan |
|---|---|---|
| Postgres 16 | `findesk-postgres` | free |
| Key Value (Redis) | `findesk-redis` | free |
| Web service (API + worker) | `findesk-api` | free |

`JWT_SECRET` and `INTERNAL_API_TOKEN` are generated automatically, and because
both processes live in one service there is nothing to copy between services.

Migrations run on every boot — the entrypoint does `alembic upgrade head` before
starting anything.

### 1.2 Optional secrets

Dashboard → `findesk-api` → **Environment**:

| Variable | Why |
|---|---|
| `GROQ_API_KEY` | vendor-name cleanup, leak narratives, vendor email drafts |
| `OPENROUTER_API_KEY` | second provider — the chain fails over on a 429 |
| `RECALL_BASE_URL` | only if you deploy Recall (§7) |

**None are required.** With no LLM key the app still works end to end: vendor
names fall back to the deterministic slug, narratives and drafts are absent, and
every rupee figure is identical — all the money math is deterministic.

### 1.3 Seed the demo data

Free instances have no shell, so run this once from your machine against the
**External** connection string (Dashboard → `findesk-postgres` → Connect):

```bash
APP_DATABASE_URL='<external connection string>' .venv/bin/python scripts/seed_dev_data.py
```

Creates the demo login, the two LeakRadar tenants (business + personal) with
their fixtures, and the chart of accounts. Idempotent — safe to re-run.

### 1.4 Verify

```bash
curl -s https://findesk-api.onrender.com/healthz
```

```bash
curl -s https://findesk-api.onrender.com/readyz
```

`readyz` should return `{"ready":true,"postgres":true,"redis":true,"recall":false}`.
`recall:false` is expected and fine.

---

## 2. UptimeRobot — keeping it awake

Render spins a free web service down after **15 minutes** without inbound
traffic, and the next request then pays a ~50 second cold start. UptimeRobot's
free plan (50 monitors, 5-minute interval) is enough to prevent that.

1. uptimerobot.com → **Add New Monitor**
2. Monitor Type: **HTTP(s)**
3. Friendly Name: `LeakRadar API`
4. URL: `https://findesk-api.onrender.com/healthz`
5. Monitoring Interval: **5 minutes**
6. Create.

**Does it actually work?** Yes — a 5-minute interval keeps the service inside
the 15-minute window, and one always-on service fits inside 750 hours/month.

Point it at `/healthz`, not `/`:

- `/healthz` is a plain liveness check with no database round-trip, so the ping
  is cheap and cannot fail because Postgres is briefly busy.
- `/` is the Next.js app on **Vercel**, which never sleeps — pinging it would
  keep nothing awake.

Because the worker shares this service, keeping the API awake keeps the worker
awake too. That is the point: a slept worker is why demo runs hang at `queued`.

One honest caveat — this keeps it *warm*, not *guaranteed*. Render can still
restart free instances. Load the app once a few minutes before you present.

---

## 3. Vercel

1. **Add New → Project** → import this repo.
2. **Root Directory: `frontend`** ← the step people miss; the build fails
   without it.
3. Framework preset and build command come from `frontend/vercel.json`.
4. **Environment Variables** → add:

   | Name | Value |
   |---|---|
   | `BACKEND_URL` | `https://findesk-api.onrender.com` (no trailing slash) |

5. Deploy. If you added `BACKEND_URL` after the first build, **redeploy** —
   `next.config.mjs` reads it at build time.

Log in with the seeded credentials; you land on **LeakRadar**.

---

## 4. Smoke-test the deploy

1. Open the app → you should land on `/leaks`.
2. Switch to **LeakRadar Demo — Business** in the tenant picker.
3. Hit **Scan for leaks**. It takes ~30s (longer if the LLM providers are slow).
4. Expect ~13 recurring vendors and roughly ₹85,000/yr recoverable, with Figma
   flagged as seat creep and Adobe/Notion as silent price rises.
5. Open `/runs` — the scan should show all 9 steps.

If the run stays at `queued`: the service is asleep (load any page and retry) or
the container is restarting — check Render → Logs.

---

## 5. Free-tier realities

Worth knowing before a demo rather than during one:

- **Free Postgres is deleted after 30 days.** Back up or upgrade before then.
  This is the one that ends a project quietly.
- **Cold start ~50s** if the service did sleep. UptimeRobot mostly prevents it.
- **SSE through the Vercel proxy** can be cut by function limits, so live
  step-streaming may stop mid-run. `useRunStream` falls back to polling, so runs
  still complete and the UI still updates — it just is not live.
- **LLM free tiers are day-capped** (Groq ~1K req/day, OpenRouter ~200). The
  chain fails over between them and then degrades to deterministic.
- **Everything shares one CPU.** A scan and a page load compete; it is a demo
  instance, not a pilot instance.

---

## 6. Going past a demo

- Split into `backend/Dockerfile` (web) + `agents/Dockerfile` (`type: worker`)
  on paid plans, so a worker crash cannot take the API with it.
- Keep the API at **one instance** until run-step consumption uses a per-replica
  consumer name. Measured: two backends sharing the one consumer group lost 2 of
  9 steps on a scan; one recorded all 9. `numInstances: 1` is pinned for this.
- Move uploads off the container filesystem to object storage.
- Migrate JWTs from localStorage to httpOnly cookies (FE4, still open).

---

## 7. Recall memory engine (optional)

Not in the blueprint. It needs Postgres+pgvector, Neo4j and its own Redis, and
Neo4j has no managed Render service — so it is left out deliberately rather than
half-wired.

Nothing breaks without it. Memory calls no-op, and LeakRadar's
usage-confirmation loop still works end to end because the human's answer is
stored on the `subscriptions` row and served by `/internal/leaks/context`. The
memory engine adds *decay and re-asking* on top; it is not the system of record.

To add it later: a pgvector Postgres, Neo4j Aura (free tier), a Redis instance,
the Recall API as a web service, and the embedding shim — then set
`RECALL_BASE_URL` on `findesk-api`.
