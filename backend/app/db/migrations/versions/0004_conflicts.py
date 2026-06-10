"""conflict cards

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conflicts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("claim_kind", sa.String(30), nullable=False, server_default="belief"),
        sa.Column("scope_key", sa.String(80), nullable=False, index=True),
        sa.Column("claim_a", sa.JSON(), nullable=False),
        sa.Column("claim_b", sa.JSON(), nullable=False),
        sa.Column("engine_view", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="open", index=True),
        sa.Column("resolution", sa.JSON(), nullable=False),
        sa.Column("resolver_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("memory_conflict_id", sa.String(36), nullable=False, unique=True),
    )


def downgrade() -> None:
    op.drop_table("conflicts")
