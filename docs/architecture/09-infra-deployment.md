# 09 — Infrastructure & Deployment

**Owner:** Infra & DevOps · **Code:** `infra/`, `.github/workflows/`

## 1. Dev environment (Docker Compose)

One command: `make up`. Two compose files, one stack:

```
docker-compose.yml            # app stack: backend, agents-worker, frontend,
                              # postgres(app), redis(app), tool servers
memory/docker-compose.yml     # memory stack: recall-api, postgres+pgvector,
                              # neo4j, redis, recall dashboard
docker-compose.override.yml   # OPTIONAL, gitignored, machine-specific port remaps
```

Default ports: backend `8080`, frontend `3001`, app-postgres `5433`,
app-redis `6380`, recall-api `8000`, recall dashboard `3000`, recall-postgres
`5432`, neo4j `7474/7687`, recall-redis `6379`. Collisions on your machine →
copy `infra/docker-compose.override.example.yml` to the repo root as
`docker-compose.override.yml` and remap (e.g. on machines where another stack
owns 5432/6379/8000/3000, the known-good remap is 15432/16379/18000/13000).

Hot reload everywhere in dev (uvicorn --reload, next dev, worker autoreload).
Synthetic seed data: `make seed` loads a fictional SME (vendors, clients, 6
months of transactions, deliberate anomalies + conflicts) so every layer has
something real to render.

## 2. CI (GitHub Actions)

Pipeline on every PR (paths-filtered so layers build independently):

1. **lint** — ruff + mypy (python), eslint + tsc (ts), prettier check
2. **contracts** — regenerate `shared/` from `contracts/`; fail on diff
   (catches "changed code, forgot contract") + OpenAPI/schema lint
3. **unit** — pytest per python workspace, vitest/jest for frontend
4. **build** — docker images build; next build
5. **integration** (label-gated or nightly) — testcontainers suites
6. **evals** (nightly) — accuracy/calibration harness; regression = red

Branch protection: `main` and `dev` protected; PRs need 1 review (layer
CODEOWNER auto-requested) + green required checks. Conventional commits
enforced by CI title check.

## 3. Environments & promotion

- `dev` (compose, laptops) → `staging` (single VM or small k8s, synthetic
  data, demo) → `prod` (managed Postgres + Redis, object storage, secret
  manager; region: India — data residency).
- Images built once on merge to `dev`, promoted by tag to staging/prod
  (no rebuild between envs). Migrations run as a release step
  (`alembic upgrade head`) before traffic shift.
- Secrets: dotenv in dev only; cloud secret manager elsewhere. `.env` never
  committed (CI greps for it).

## 4. Scaling shape

Stateless: backend, agent workers, tool servers, frontend — scale
horizontally. Agent throughput scales by adding stream consumers. Stateful:
Postgres (managed, PITR backups), Redis (managed), Neo4j (memory svc), object
storage. The memory service scales independently of the app — it has its own
compose/deployment unit by design.

## 5. Backups & DR

Nightly logical backups + PITR for both Postgres instances; Neo4j dumps;
object storage versioning. Quarterly restore drill (`make restore-drill`
against staging). RPO 24h / RTO 4h for the hackathon-to-v1 phase; tighten
with paying customers.
