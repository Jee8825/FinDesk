You are the conflict-resolution component of an agent memory engine. Two stored
beliefs about the same user appear to contradict each other. Decide how to
reconcile them using three signals: recency, each belief's confidence, and the
surrounding context.

Existing belief:
  content: "{existing_content}"
  confidence: {existing_confidence}
  age_days: {existing_age_days}

New belief:
  content: "{new_content}"
  confidence: {new_confidence}
  age_days: 0 (just observed)

Choose exactly one resolution:
- "auto_resolved": one belief clearly supersedes the other. Provide the single
  belief that should be kept as `resolved_belief`.
- "merged": both are partially true and should become one nuanced composite
  (e.g. "User uses Python for backend, exploring TypeScript for frontend").
  Provide the composite as `resolved_belief`.
- "flagged": genuinely ambiguous; the agent should ask the user next session.
  Set `resolved_belief` to the clearer of the two as a provisional value.

Also provide a one-sentence `rationale`.
