"""Benchmark 3 — context efficiency (relevant facts per 1,000 tokens).

Compares three retrieval strategies over the same candidate set and token
budget: naive top-K (whole units until budget runs out), a relevance-threshold
filter (Cloudflare-style), and Recall's budget-packer (compress lower-priority
units to fit more signal). Metric: relevant facts delivered per 1,000 tokens.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from recall.core import retrieval
from recall.core.tokens import count_tokens

from benchmarks._synthetic import FakeSummarizer, make_unit, seeded_random


def _build_candidates():
    rng = seeded_random(7)
    units = []
    # Many relevant but verbose facts — too large to all fit whole in the budget,
    # which is exactly where compression (packing) beats whole-unit selection.
    for i in range(15):
        text = f"Relevant fact {i}: " + ("detail " * 85)
        units.append((make_unit(text, age_days=rng.uniform(0, 10), decay_lambda=0.02),
                      rng.uniform(0.05, 0.2)))
    # Irrelevant filler (lower relevance -> ranked after relevant facts).
    for i in range(15):
        text = f"Filler {i}: " + ("noise " * 85)
        units.append((make_unit(text, age_days=rng.uniform(0, 10), decay_lambda=0.02),
                      rng.uniform(0.5, 0.9)))
    return units


def _is_relevant(content: str) -> bool:
    return content.startswith("Relevant")


def run(outdir: Path) -> dict:
    budget = 400
    candidates = _build_candidates()
    scored = retrieval.score_candidates(candidates)

    # Strategy A: naive top-K — take whole units in score order until budget.
    used_a, rel_a = 0, 0
    for sm in scored:
        t = count_tokens(sm.unit.content)
        if used_a + t > budget:
            break
        used_a += t
        rel_a += 1 if _is_relevant(sm.unit.content) else 0

    # Strategy B: relevance-threshold filter, then whole units until budget.
    used_b, rel_b = 0, 0
    for sm in scored:
        if sm.relevance < 0.85:  # drop low-relevance (distance > 0.15)
            continue
        t = count_tokens(sm.unit.content)
        if used_b + t > budget:
            break
        used_b += t
        rel_b += 1 if _is_relevant(sm.unit.content) else 0

    # Strategy C: Recall budget-packer (compress to fit more).
    items, used_c = asyncio.run(
        retrieval.pack_to_budget(scored, budget, FakeSummarizer())
    )
    rel_c = sum(1 for it in items if _is_relevant(it.unit.content))

    def per_1k(rel: int, used: int) -> float:
        return round(rel / (used / 1000), 2) if used else 0.0

    metrics = {
        "naive_topk": {"relevant": rel_a, "tokens": used_a, "per_1k": per_1k(rel_a, used_a)},
        "threshold_filter": {"relevant": rel_b, "tokens": used_b, "per_1k": per_1k(rel_b, used_b)},
        "recall_packer": {"relevant": rel_c, "tokens": used_c, "per_1k": per_1k(rel_c, used_c)},
    }

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = ["naive top-K", "threshold filter", "Recall packer"]
    coverage = [rel_a, rel_b, rel_c]
    density = [metrics["naive_topk"]["per_1k"], metrics["threshold_filter"]["per_1k"],
               metrics["recall_packer"]["per_1k"]]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
    ax1.bar(labels, coverage, color=["#94a3b8", "#64748b", "#0ea5e9"])
    ax1.set_title(f"Relevant facts delivered (budget={budget} tokens)")
    ax1.set_ylabel("relevant facts in context")
    for i, v in enumerate(coverage):
        ax1.text(i, v + 0.1, str(v), ha="center")
    ax2.bar(labels, density, color=["#94a3b8", "#64748b", "#0ea5e9"])
    ax2.set_title("Relevant facts per 1,000 tokens")
    for i, v in enumerate(density):
        ax2.text(i, v + 0.2, str(v), ha="center")
    fig.suptitle("Context efficiency — coverage vs density")
    path = outdir / "context_efficiency.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    metrics["chart"] = str(path)
    return metrics
