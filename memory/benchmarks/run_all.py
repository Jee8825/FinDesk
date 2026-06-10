"""Run all benchmarks and write charts + a JSON summary to benchmarks/output/."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks import context_efficiency, forgetting_curve, recall_snr


def main() -> None:
    outdir = Path(__file__).resolve().parent / "output"
    outdir.mkdir(parents=True, exist_ok=True)

    results = {
        "forgetting_curve": forgetting_curve.run(outdir),
        "recall_snr": recall_snr.run(outdir),
        "context_efficiency": context_efficiency.run(outdir),
    }

    summary = outdir / "summary.json"
    summary.write_text(json.dumps(results, indent=2))

    print("Benchmark results:")
    print(json.dumps(results, indent=2))
    print(f"\nCharts + summary written to {outdir}/")


if __name__ == "__main__":
    main()
