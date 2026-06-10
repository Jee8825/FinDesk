"""B4: working-capital actions

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wc_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, index=True),  # treds|collect|retime
        sa.Column(
            "invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), nullable=False, index=True
        ),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("client", sa.String(200), nullable=False),
        sa.Column("unlock_paise", sa.BigInteger(), nullable=False),
        sa.Column("cost_paise", sa.BigInteger(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="proposed", index=True
        ),
        sa.Column("approval_id", sa.String(36), nullable=True),
        sa.Column("execution", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("wc_actions")
