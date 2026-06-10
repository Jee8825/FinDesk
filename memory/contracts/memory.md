# Memory Contract (v1)

## Tiers
| Tier | Contents | Decay (λ /day) | Promotion |
|---|---|---|---|
| episodic | raw timestamped events | 0.35 (days) | → semantic via consolidation |
| semantic | facts, preferences, entities | 0.02 (weeks) | → procedural on repeated patterns |
| procedural | learned workflows | 0.001 (near-permanent) | terminal |

## The two axes (orthogonal)
- **strength** ∈ (0,1]: retrieval priority. `S(t)=S₀·e^(−λt)`; ×r (1.25) on retrieval; tombstoned below τ (0.05).
- **confidence** ∈ [0,1]: trust. +Δ on corroboration (diminishing), −Δ on contradiction, drift on dormancy, crystallized ≥ 0.95.

## Lifecycle states
`active` → `tombstoned` (soft delete, compacted after retention) · `crystallized` (high-confidence, decay paused).

## Scopes
`private` · `team` (needs team_id) · `global` (orchestrator-only write) · `user-owned` (GDPR-visible, user-deletable).

**Hard rule:** changing decay/confidence formulas or tier semantics is a breaking
change — update this contract and the benchmark baselines.
