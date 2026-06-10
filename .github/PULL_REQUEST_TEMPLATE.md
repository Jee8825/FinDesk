## What & why

<!-- One paragraph. Link the issue. -->

## Layer(s) touched

- [ ] agents · [ ] tools · [ ] memory · [ ] backend · [ ] frontend · [ ] infra
- [ ] contracts / shared (⇒ both affected owners must review)
- [ ] prompts (⇒ eval note below)
- [ ] guardrails / policies (⇒ ADR linked)

## Contract check

- [ ] No cross-layer shape changed, **or** `contracts/` updated in this PR and `make contracts` output committed
- [ ] Breaking change? → protocol followed (announce + version bump + migration issue): <!-- link -->

## AI-generated code disclosure

<!-- Which parts were agent-generated? Reviewers look hardest there
     (invented fields, duplicated logic, implementation-shaped tests). -->

## Verification

<!-- Commands run + observed results. "Agent said it passes" is not verification. -->

- [ ] `make lint` clean
- [ ] `make test` green locally
- [ ] UI change: loading/empty/error states included; screenshots attached
- [ ] Accuracy-relevant change: eval fixture added/updated

## Feature-map check

Per [docs/architecture/10-module-feature-map.md](../docs/architecture/10-module-feature-map.md):
all required layers touched, or explained here why not.
