"""Benchmark 1 — forgetting-curve validation.

The visually compelling one: memory strength over time, with and without
retrieval reinforcement, per tier. Demonstrates that Recall's memories fade
unless used — and that using them keeps them alive.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

from recall.config import get_settings
from recall.core import decay


def _series(lam: float, days: int, reinforce_every: int, r: float):
    plain, reinforced = [], []
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    plain_anchor = now
    reinf_anchor = now
    reinf_s0 = 1.0
    for d in range(days + 1):
        t = now + timedelta(days=d)
        plain.append(decay.current_strength(1.0, lam, plain_anchor, t))
        s = decay.current_strength(reinf_s0, lam, reinf_anchor, t)
        if reinforce_every and d > 0 and d % reinforce_every == 0:
            s = min(1.0, s * r)
            reinf_s0 = s
            reinf_anchor = t
        reinforced.append(s)
    return plain, reinforced


def run(outdir: Path) -> dict:
    settings = get_settings()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    days = 30
    every = 2
    lam = settings.decay_lambda("episodic")
    plain, reinforced = _series(lam, days, reinforce_every=every, r=settings.reinforcement_factor)
    xs = list(range(days + 1))
    ax.plot(xs, plain, label="no retrieval (fades to tombstone)", color="#94a3b8")
    ax.plot(
        xs, reinforced, label=f"retrieved every {every}d (stays alive)",
        color="#0ea5e9", linewidth=2,
    )
    ax.axhline(settings.tombstone_threshold, ls="--", color="#ef4444", label="tombstone τ")
    ax.set_title(f"Forgetting curve — episodic tier (λ={lam:.2f}/day)")
    ax.set_xlabel("days")
    ax.set_ylabel("strength")
    ax.legend()
    ax.grid(alpha=0.2)
    path = outdir / "forgetting_curve.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    mean_plain = sum(plain) / len(plain)
    mean_reinforced = sum(reinforced) / len(reinforced)
    return {
        "chart": str(path),
        "mean_strength_plain": round(mean_plain, 4),
        "mean_strength_reinforced": round(mean_reinforced, 4),
        "reinforcement_advantage": round(mean_reinforced / max(mean_plain, 1e-9), 2),
    }
