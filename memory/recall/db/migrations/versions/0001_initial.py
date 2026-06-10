"""initial schema: pgvector extension + all tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-07

The first migration enables the ``vector`` extension and then materializes the
full ORM metadata, guaranteeing the initial schema matches the SQLAlchemy
models. Subsequent migrations should be created with ``alembic revision
--autogenerate`` so they capture incremental diffs.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from recall.db.models import Base

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
