"""Recall engine — the intelligence layer above raw storage.

Modules:
    decay        — Ebbinghaus strength decay + retrieval reinforcement
    ingestion    — heavy-LLM fact extraction into tiered memory units
    retrieval    — relevance x recency x strength scoring + token-budget packing
    conflict     — contradiction detection + LLM resolution
    provenance   — evidence-chain bookkeeping (Neo4j)
    confidence   — cross-session epistemic confidence accumulation
    consolidation— scheduled tier promotion + procedural crystallization
    prefetch     — predictive warm-cache of likely memory clusters
    scoping      — cross-agent permission layer
    engine       — façade wiring the above into the public operations
"""
