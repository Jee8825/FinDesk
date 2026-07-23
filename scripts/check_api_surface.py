#!/usr/bin/env python3
"""B4 guard (crucible-layer-audit): the mounted FastAPI surface and
contracts/api.yaml must name the same operations.

Request/response *shapes* are hand-mirrored under review (schema codegen is
roadmap); this check makes the *surface* impossible to drift silently:

- every route the app mounts under /api/v1 must be declared in the contract
  (no undocumented surface), and
- every declared path must actually be mounted (no phantom claims — the
  original lap-1 failure mode, mechanized away).

Worker-internal routes (mounted without the /api/v1 prefix) and the root
health probes are exempt by construction. Exit 1 on any drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

HTTP = {"GET", "POST", "PUT", "PATCH", "DELETE"}
PREFIX = "/api/v1"


def spec_ops() -> set[tuple[str, str]]:
    spec = yaml.safe_load((ROOT / "contracts" / "api.yaml").read_text())
    ops: set[tuple[str, str]] = set()
    for path, item in spec.get("paths", {}).items():
        for method in item:
            if method.upper() in HTTP:
                ops.add((method.upper(), path))
    return ops


def app_ops() -> set[tuple[str, str]]:
    from app.main import create_app

    ops: set[tuple[str, str]] = set()
    for route in create_app().routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if not path.startswith(PREFIX + "/"):
            continue  # worker-internal + health probes are out of contract scope
        for method in set(methods) & HTTP:
            ops.add((method, path[len(PREFIX) :]))
    return ops


def main() -> int:
    declared, mounted = spec_ops(), app_ops()
    undocumented = sorted(mounted - declared)
    phantom = sorted(declared - mounted)
    for method, path in undocumented:
        print(f"UNDOCUMENTED  {method:6} {path}   (mounted, missing from contracts/api.yaml)")
    for method, path in phantom:
        print(f"PHANTOM       {method:6} {path}   (declared, not mounted by the app)")
    if undocumented or phantom:
        print(f"\ncontract surface drift: {len(undocumented)} undocumented, {len(phantom)} phantom")
        return 1
    print(f"contract surface clean: {len(mounted)} operations match contracts/api.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
