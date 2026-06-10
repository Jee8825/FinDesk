"""Benchmark 2 — long-horizon recall signal-to-noise.

Simulates multi-session histories with deliberately injected *stale* memories:
facts that were once relevant but are now outdated. We compare top-K retrieval
ranked by relevance alone (naive / Mem0-style additive) vs Recall's
relevance × strength (decay-aware). Metric: precision@K against ground truth
(currently-relevant, non-stale memories).
"""

from __future__ import annotations

from pathlib import Path

from recall.config import get_settings
from recall.core import decay

from benchmarks._synthetic import make_unit, seeded_random


def _precision_at_k(ranked: list[tuple[bool, float]], k: int) -> float:
    top = ranked[:k]
    return sum(1 for is_good, _ in top if is_good) / max(1, len(top))


def run(outdir: Path) -> dict:
    settings = get_settings()
    rng = seeded_random()
    lam = settings.decay_lambda("semantic")
    k = 5
    n_cases = 50

    naive_scores, decay_scores = [], []
    for _ in range(n_cases):
        units: list[tuple] = []  # (unit, distance, is_currently_relevant)
        # Fresh relevant facts (recent, on-topic).
        for i in range(k):
            u = make_unit(f"topic fact fresh {i}", age_days=rng.uniform(0, 3), decay_lambda=lam)
            units.append((u, rng.uniform(0.02, 0.15), True))
        # Stale "noise": once on-topic, now old and outdated (should be demoted).
        for i in range(k):
            u = make_unit(f"topic fact stale {i}", age_days=rng.uniform(120, 400), decay_lambda=lam)
            units.append((u, rng.uniform(0.02, 0.15), False))
        # Unrelated filler.
        for i in range(10):
            u = make_unit(f"unrelated filler {i}", age_days=rng.uniform(0, 60), decay_lambda=lam)
            units.append((u, rng.uniform(0.4, 0.9), False))

        # naive: rank by relevance only.
        naive = sorted(
            ((good, 1 - dist) for u, dist, good in units), key=lambda x: x[1], reverse=True
        )
        # decay-aware: relevance * current strength.
        decay_ranked = []
        for u, dist, good in units:
            s = decay.current_strength(u.strength, u.decay_lambda, u.strength_updated_at)
            decay_ranked.append((good, (1 - dist) * s))
        decay_ranked.sort(key=lambda x: x[1], reverse=True)

        naive_scores.append(_precision_at_k(naive, k))
        decay_scores.append(_precision_at_k(decay_ranked, k))

    naive_avg = sum(naive_scores) / n_cases
    decay_avg = sum(decay_scores) / n_cases

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(["naive (relevance only)", "Recall (decay-aware)"], [naive_avg, decay_avg],
           color=["#94a3b8", "#0ea5e9"])
    ax.set_ylim(0, 1)
    ax.set_ylabel(f"precision@{k}")
    ax.set_title("Long-horizon recall: signal-to-noise\n(stale memories injected)")
    for i, v in enumerate([naive_avg, decay_avg]):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center")
    path = outdir / "recall_snr.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    return {
        "chart": str(path),
        "precision_at_k_naive": round(naive_avg, 4),
        "precision_at_k_recall": round(decay_avg, 4),
        "improvement": round(decay_avg - naive_avg, 4),
    }
