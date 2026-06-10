"""B2: invoice acceptance dates + statutory clocks

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices", sa.Column("acceptance_date", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "statutory_clocks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column(
            "invoice_id",
            sa.String(36),
            sa.ForeignKey("invoices.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("acceptance_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("statutory_due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("overdue_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accrued_interest_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("annual_rate_bps", sa.Integer(), nullable=False),
        sa.Column(
            "escalation_level", sa.String(20), nullable=False, server_default="none", index=True
        ),
    )


def downgrade() -> None:
    op.drop_table("statutory_clocks")
    op.drop_column("invoices", "acceptance_date")
