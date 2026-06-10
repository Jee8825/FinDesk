# scripts/

Repo-level operational scripts (referenced by the Makefile):

- `gen_contracts.py` — generate `shared/py` + `shared/ts` from `contracts/` (TODO)
- `seed_dev_data.py` — synthetic SME fixture: vendors, clients, 6 months of
  transactions, planted duplicates/overcharges/conflicts (TODO)
- `smoke_e2e.py` — weekly end-to-end smoke: ingest → reconcile → resolve one
  conflict → approve one email → forecast renders (TODO)
- `purge_tenant.py` — audited offboarding: app DB + memory atomic delete +
  object storage prefix (TODO)
