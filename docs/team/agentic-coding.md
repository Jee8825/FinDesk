# Agentic Coding — Multi-Agent Team Protocol

Every team member works with an AI coding agent (Claude Code, Cursor, etc.).
That means at any moment **up to 8 agent instances are generating code against
this repo in parallel**. These rules keep that productive instead of chaotic.
They bind the humans; the context files make them bind the agents too.

## 1. Context file hierarchy (how agents learn the rules)

```
CLAUDE.md                  # root: stack, architecture, hard rules — ALWAYS loaded
agents/CLAUDE.md           # layer rules: graph conventions, no vendor SDKs, prompt loading
backend/CLAUDE.md          # layer rules: router/service/repo split, migrations, money-in-paise
frontend/CLAUDE.md         # layer rules: generated client only, feature folders, a11y bars
tools/CLAUDE.md            # layer rules: no business logic, contract versioning, idempotency
memory/CLAUDE.md           # vendored Recall's own context + FinDesk extension boundaries
```

- Start every session in the folder of the layer you own, so your agent loads
  root + layer context.
- Context files are **production code**: versioned, reviewed, updated at the
  Friday sync, never stale. If your agent made a wrong architectural
  assumption, the fix is usually a context-file PR — make it.

## 2. The blast-radius rule

> An agent session may write only inside the layer its operator owns, plus
> `contracts/` and `prompts/` for that layer. Everything else is read-only
> context.

- Need a change in another layer? You have three legal moves: (a) open an
  issue tagging the owner, (b) propose a contract change PR, (c) pair with the
  owner in *their* session. You never have a fourth move: editing their
  internals "to make it work" — that's how two agents create interlocking
  regressions nobody understands.
- Exception: repo-wide mechanical chores (rename, dep bump) — announce first,
  one PR, one author, no concurrent feature merges.

## 3. Contract-first is agent-first

Agents are *worse* than humans at noticing implicit shape drift and *better*
at staying inside explicit schemas. So:

- Point your agent at `contracts/` **before** it writes code that crosses a
  layer boundary; the generated models in `shared/` are the only legal way to
  consume another layer's shapes.
- If the agent invents a field, endpoint, or tool parameter that isn't in a
  contract, that's a hallucination by definition — reject it in review even
  if it "works locally".

## 4. Session hygiene

- **One branch, one task, one session.** Don't let a single agent session
  sprawl across multiple features; merge conflicts multiply with session length.
- Rebase on `dev` before starting and before opening the PR; with 8 parallel
  agents, integration debt compounds within hours, not days.
- Commit early with conventional messages; agents that commit in reviewable
  increments are debuggable, agents that dump 4k-line diffs are not.
- Before opening a PR: `make lint && make test && make contracts` locally —
  don't make CI the first reviewer of obvious breakage.

## 5. Review rules for AI-generated code

- Same scrutiny as human code. Specifically check the three classic agent
  failure modes: (1) invented APIs/fields not in contracts, (2) silent
  duplication of logic that already exists in another module, (3) tests that
  assert the implementation rather than the behavior.
- The PR template asks which parts are agent-generated — answer honestly; it
  tells the reviewer where to look hardest.
- Reviewer may run the author's stated verification steps; "the agent said it
  passes" is not verification.

## 6. Things no agent may ever be asked to do

- Weaken or bypass guardrails (P1–P6 in
  [05-guardrails.md](../architecture/05-guardrails.md)) — including "just for
  this test".
- Commit secrets, real customer data, or live credentials into the repo or
  into fixtures.
- Modify `memory/` core engine math without an ADR (see vendoring policy in
  [03-memory-recall.md](../architecture/03-memory-recall.md)).
- Hand-edit generated code in `shared/` or hardcode a prompt outside `prompts/`.

## 7. Shared prompt library

`prompts/` is part of the product, owned per layer, versioned
(`name@v3.md` + changelog header). New prompt versions ship alongside the old
one; the old version is removed only after the eval harness confirms no
regression. Prompt diffs get reviewed like logic diffs — because they are.

## 8. The mental-model problem

With 8 humans + 8 agents, nobody holds the whole system in their head — the
docs do. When reality and `docs/architecture/` diverge, **fixing the doc is
part of the change that caused the divergence**, not a cleanup for later. An
agent reading stale architecture docs will confidently build against a system
that no longer exists.
