"""A6: anomaly cards

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anomalies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("kind", sa.String(20), nullable=False, index=True),
        sa.Column("severity", sa.String(8), nullable=False, server_default="medium"),
        sa.Column("vendor_label", sa.String(80), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("recommended_action", sa.String(300), nullable=False),
        sa.Column("recoverable_paise", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="open", index=True),
        sa.Column("decided_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("dedupe_key", sa.String(64), nullable=False, unique=True),
    )


def downgrade() -> None:
    op.drop_table("anomalies")
