# infra/

Docker, CI/CD, environments, observability pipeline. Deep-dive:
`docs/architecture/09-infra-deployment.md`.

- `docker-compose.override.example.yml` — machine-specific port remap template
  (copy to repo root as `docker-compose.override.yml`, gitignored)
- `observability/` — Langfuse/OTel config + eval harness (`evals/`) — see
  `docs/architecture/08-observability.md`

Owned by the rotating Infra & DevOps member; new compose services and env vars
go through this owner.
