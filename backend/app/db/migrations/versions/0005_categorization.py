"""A3: chart of accounts + transaction categorization columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chart_of_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("type", sa.String(12), nullable=False),
        sa.UniqueConstraint("tenant_id", "code"),
    )
    op.add_column(
        "bank_transactions", sa.Column("category_code", sa.String(40), nullable=True, index=True)
    )
    op.add_column(
        "bank_transactions", sa.Column("category_source", sa.String(12), nullable=True)
    )
    op.add_column(
        "bank_transactions", sa.Column("category_confidence", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("bank_transactions", "category_confidence")
    op.drop_column("bank_transactions", "category_source")
    op.drop_column("bank_transactions", "category_code")
    op.drop_table("chart_of_accounts")
