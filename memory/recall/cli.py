"""Minimal CLI: serve the API or run datastore initialization.

    recall serve            # run the API with uvicorn
    recall init-db          # apply Alembic migrations + Neo4j constraints
"""

from __future__ import annotations

import argparse
import asyncio


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("recall.api.app:app", host=args.host, port=args.port, reload=args.reload)


def _init_db(_: argparse.Namespace) -> None:
    import subprocess

    subprocess.run(["alembic", "upgrade", "head"], check=True)

    from recall.db import close_driver, init_schema

    async def _neo4j() -> None:
        await init_schema()
        await close_driver()

    asyncio.run(_neo4j())
    print("init-db complete: migrations applied, Neo4j constraints created.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="recall", description="Recall memory engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the API server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=_serve)

    init = sub.add_parser("init-db", help="apply migrations and Neo4j constraints")
    init.set_defaults(func=_init_db)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
