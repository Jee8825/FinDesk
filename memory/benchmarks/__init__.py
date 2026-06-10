"""Recall benchmark suites.

Each module exposes ``run(outdir) -> dict`` that computes metrics and writes a
chart. ``run_all`` executes all of them. The suites are deterministic and run
offline (no datastores, no API keys): they exercise the real engine math
(decay, scoring, budget-packing) against synthetic data so the headline claims
are reproducible.
"""
