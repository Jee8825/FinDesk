# scripts/

Repo-level operational scripts (referenced by the Makefile):

- `gen_contracts.py` — generate `shared/py` + `shared/ts` (+ frontend copy)
  from `contracts/api.yaml`; CI fails on drift
- `seed_dev_data.py` — dev seed. Phase 0: demo tenant + owner login. Grows
  into the synthetic SME (vendors, clients, 6mo txns, planted anomalies)
- `smoke_memory.py` — ingest/retrieve one claim against the Recall stack
- `smoke_e2e.py` — weekly end-to-end smoke: ingest → reconcile → resolve one
  conflict → approve one email → forecast renders (TODO, Phase 2)
- `purge_tenant.py` — audited offboarding: app DB + memory atomic delete +
  object storage prefix (TODO, Phase 5)
