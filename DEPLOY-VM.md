# Full-stack deploy on one VM — memory engine included

The "no compromise" option: app plane **and** the Recall memory engine on a
single box, frontend still on Vercel.

Use this instead of [DEPLOY.md](DEPLOY.md) (Render) when the memory engine has
to be live.

```
Vercel (Next.js) ──▶ Caddy :443 ──▶ api (FastAPI + agents worker)
                                      ├─▶ app-postgres, app-redis
                                      └─▶ recall-api
                                            ├─▶ recall-postgres (pgvector)
                                            ├─▶ recall-neo4j
                                            ├─▶ recall-redis
                                            └─▶ embedding-shim
```

## Why one VM rather than a PaaS

Per-service free tiers cannot hold this stack. Measured idle footprint:

| Component | RAM |
|---|---|
| Neo4j | **571 MiB** |
| Recall API | 190 MiB |
| api (backend + worker) | 136 MiB |
| embedding shim | 96 MiB |
| Recall Postgres | 58 MiB |
| app Postgres | 34 MiB |
| both Redis | 19 MiB |
| **Total** | **1105 MiB** |

Measured with every service running together *after* a full agent scan, not
summed from separate idle runs. Idle is ~940 MiB; the ~165 MiB delta is what a
scan costs.

Neo4j alone rules out every 1 GB free container plan, and Recall imports it in
`api/app.py` with no optional flag. One VM has no per-service caps, no cold
starts and no request-count limits.

## Choosing a box

| Option | Spec | Verdict |
|---|---|---|
| **Oracle Always Free** | 2 OCPU / 12 GB ARM | **Best.** Free forever, huge headroom. Cost: card for identity verification, and ARM capacity is often queued — start days early. |
| AWS `t4g.medium` | 2 vCPU / 4 GB ARM | Comfortable. ~$24/mo — about 4–8 months on the $100–200 new-account credits. |
| AWS `t4g.small` | 2 vCPU / 2 GB ARM | Runs it, tight. ~$12/mo on credits. |
| AWS `t3.micro` (12-mo free tier) | 2 vCPU / **1 GB** | **Does not fit.** Neo4j is 614 MB idle. |

On AWS the free tier depends on account age: accounts created **before 15 July
2025** get 12 months of `t3.micro` (too small); accounts created **after** get
$100–200 credits for 6 months and no free EC2 hours. Either way, the free
*allowance* does not cover this stack — credits do.

Everything below is identical on Oracle, AWS, Hetzner or any Ubuntu box.

## 1. Prepare the VM

Ubuntu 22.04/24.04, ports **80** and **443** open in the cloud firewall
(Oracle: Security List ingress; AWS: Security Group inbound).

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER && newgrp docker
```

On a 2 GB box add swap, so a build spike fails slowly instead of OOM-killing
Neo4j:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

```bash
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. Clone and configure

```bash
git clone https://github.com/Jee8825/FinDesk.git && cd FinDesk
```

```bash
cp .env.vm.example .env.vm
```

Generate a secret for each blank (`openssl rand -hex 32`), then edit `.env.vm`.
Set `SITE_ADDRESS` to your domain for automatic HTTPS, or leave `:80` while DNS
is still pointing.

The compose file fails fast with a named error if any required secret is
missing, rather than starting a stack with a default password.

## 3. Bring it up

```bash
docker compose --env-file .env.vm -f infra/docker-compose.vm.yml up -d --build
```

First build takes ~5–10 minutes on 2 vCPU. Then:

```bash
docker compose --env-file .env.vm -f infra/docker-compose.vm.yml ps
```

```bash
curl -s localhost/readyz
```

Expect `{"ready":true,"postgres":true,"redis":true,"recall":true}` — **`recall:true`
is the whole point of this file.** If it is false, check `docker compose logs recall-api`.

`readyz` only proves the API can *reach* Recall. To prove memory actually works,
make it store and retrieve something:

```bash
docker compose --env-file .env.vm -f infra/docker-compose.vm.yml exec -T recall-api python -c "
import json,urllib.request
def post(p,b):
    r=urllib.request.Request('http://localhost:8000'+p,data=json.dumps(b).encode(),headers={'Content-Type':'application/json'},method='POST')
    return json.loads(urllib.request.urlopen(r,timeout=90).read())
post('/memory/ingest',{'user_id':'vendor:test','session_id':'smoke','content':'The user no longer uses the subscription Test Co.'})
print(post('/memory/retrieve',{'user_id':'vendor:test','query':'does the user still use this','limit':3}))"
```

One unit back means embeddings, pgvector, Neo4j and the shim are all wired
correctly. This check exists because three separate misconfigurations all left
the stack *looking* healthy while ingest returned 500 — see §9.

## 4. Seed

`scripts/` is not baked into the image, so copy it in and run it there — the
image already has every dependency the seed needs, and Postgres is not exposed
to the host:

```bash
docker compose --env-file .env.vm -f infra/docker-compose.vm.yml cp scripts api:/srv/scripts
```

```bash
docker compose --env-file .env.vm -f infra/docker-compose.vm.yml exec -T api sh -c 'cd /srv && python scripts/seed_dev_data.py'
```

Expect it to report the demo login, `LeakRadar Demo — Business` (80 debits) and
`LeakRadar Demo — Personal` (81 debits). Idempotent — safe to re-run.

## 5. Vercel

Same as [DEPLOY.md §3](DEPLOY.md), with one change: set `BACKEND_URL` to your VM
(`https://api.yourdomain.com`, or `http://<vm-ip>` while testing). Redeploy after
setting it — `next.config.mjs` reads it at build time.

## 6. Security

The compose publishes **only** ports 80/443 via Caddy. Postgres, Neo4j, Redis,
the embedding shim and the Recall API have no published ports and are reachable
only on the private compose network. Do not "temporarily" publish Neo4j or
Postgres to debug — an internet-reachable Neo4j is how demo boxes get owned.

For shell access use:

```bash
docker compose --env-file .env.vm -f infra/docker-compose.vm.yml exec recall-neo4j cypher-shell -u neo4j
```

## 7. Operating it

```bash
docker compose --env-file .env.vm -f infra/docker-compose.vm.yml logs -f api
```

```bash
docker stats --no-stream
```

Watch Neo4j: its heap is pinned small (384 MB max) on purpose, because the
default sizes off host RAM and on a 2 GB box would starve everything else. If
you move to a bigger box, raise `NEO4J_server_memory_heap_max__size`.

Update:

```bash
git pull && docker compose --env-file .env.vm -f infra/docker-compose.vm.yml up -d --build
```

Migrations run on every `api` boot, so a pull-and-up is a complete deploy.

## 8. Three ways this looks healthy while being broken

All three were hit building this, and each survives a green `docker compose ps`:

1. **The embedding shim binds `127.0.0.1`.** Its `__main__` block is written for
   the dev-host recipe, so in a container it is unreachable from siblings — and a
   healthcheck that curls localhost *inside* the container passes happily.
   `infra/Dockerfile.shim` serves the module's `app` object with
   `--host 0.0.0.0` instead. **Never health-check a service from itself.**
2. **Recall's image omits `prompts/`.** `recall.core.prompts` resolves
   `/app/prompts` at request time, so ingest 500s with "prompt template not
   found" long after startup succeeds. Mounted read-only from `memory/prompts`.
3. **Embedding dimensions must match the model.** The shim's potion-base-8M emits
   256 dims; Recall defaults to 1024 for qwen. The pgvector column is created at
   that width, so every ingest fails with "expected 1024 dimensions, not 256".
   `RECALL_EMBEDDING_DIM: 256` is pinned in the compose.

If you swap the embedding model, change that dimension **and** recreate the
Recall volume — the column width is fixed at creation.

## 9. What you gain over the Render path

Only this: the memory engine is live, so vendor-usage answers **decay** and get
re-asked, conflicting beliefs surface, and semantic recall works across
observations. Everything else is identical — the LeakRadar loop, all the money
math, the approval gate and the statutory clocks work on either deployment,
because the usage answer is stored on the `subscriptions` row and Recall layers
decay on top rather than being the system of record.

Worth being clear-eyed: that is a real differentiator to demo, and it costs you a
VM to babysit. Render is one click and never pages you.
