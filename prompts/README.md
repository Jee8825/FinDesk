# prompts/ — Shared Prompt Library

Every LLM prompt in the system lives here, loaded by name+version. No inline
prompt strings anywhere in `agents/`, `backend/`, or `tools/` (and `memory/`
loads its own from `memory/prompts/`).

## Layout

```
agents/    # planner, executor steps, critic, narration — per graph
memory/    # NOTE: finance extraction/consolidation prompts live in memory/prompts/
           # (the vendored engine loads from its own tree); this folder holds
           # only their design notes + eval fixtures
```

## Versioning

`<name>@v<N>.md` with a changelog header (date, author, eval result). New
versions ship **alongside** old ones; remove the old version only after the
eval harness shows no regression. Prompt diffs are logic diffs — they get the
same review.
