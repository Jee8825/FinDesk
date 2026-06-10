"""approvals queue

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("action_kind", sa.String(40), nullable=False, index=True),
        sa.Column("action_payload", sa.JSON(), nullable=False),
        sa.Column("action_hash", sa.String(64), nullable=False),
        sa.Column("requested_by", sa.JSON(), nullable=False),
        sa.Column("policy_verdicts", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending", index=True),
        sa.Column("decider_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rationale", sa.String(500), nullable=True),
        sa.Column("token_id", sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("approvals")
