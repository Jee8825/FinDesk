# shared/ — Generated Contract Models + Cross-Layer Utilities

- `py/` — Pydantic models generated from `contracts/` + shared utilities
  (telemetry redaction wrapper, money/paise helpers, UUIDv7).
- `ts/` — TypeScript API client + types generated from `contracts/api.yaml`.

**Never hand-edit generated files.** `make contracts` regenerates; CI fails on
drift between `contracts/` and committed output. Utilities (non-generated) are
the only hand-written code here and need review from both Python and TS sides
when they encode conventions (e.g. paise formatting).
