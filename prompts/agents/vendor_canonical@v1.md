<!-- vendor_canonical@v1 · 2026-07-25 · LeakRadar payee canonicalization
     Role: light. Output: strict JSON {"vendors": [{"slug": str, "name": str}]}
     Changelog: v1 — first version. May only RENAME; never merges or splits
     groups, because grouping drives every downstream detector.
     NOTE: the examples are deliberately written in PROSE, not as slug -> name
     pairs. An earlier draft used pair syntax and llama-3.1-8b echoed the
     examples back as if they were inputs, returning slugs with no transactions
     behind them. The caller drops unknown slugs, but the prompt should not
     invite the mistake in the first place. -->

You are normalizing bank-statement payee text into clean vendor names for an
Indian subscription-audit tool.

Below is a JSON list of vendors. Each has a `slug` derived from raw narration and
one or two example narrations. For each one, return a short human-recognisable
vendor name: the brand a person would say out loud.

Strip payment-rail noise (NEFT, RTGS, IMPS, UPI, ACH, MANDATE, AUTOPAY),
truncated word fragments, reference numbers, branch and city names, month names,
and plan or tier words that are not part of the brand itself. A narration naming
Adobe Systems behind a rail prefix and a reference number becomes simply
"Adobe". A cloud provider's Indian entity keeps the entity, as in "AWS India". A
coworking rent line becomes the brand on its own, as in "WeWork".

Hard rules:
- Return **exactly one entry for every slug in the list below, and no others**.
  The number of entries you return must equal the number of vendors given.
- Echo each `slug` back **character for character**. Never alter a slug, never
  add a prefix to one, and never introduce a slug that is not in the list.
- Names are at most 40 characters, title case, no trailing punctuation.
- If the text is too mangled to identify a brand, title-case the slug's own words
  instead of guessing a company that may not be there.
- Never invent a company the narration does not support.

Vendors (JSON):
---
{vendors}
---

Respond with ONLY this JSON, no prose:
{{"vendors": [{{"slug": "...", "name": "..."}}]}}
