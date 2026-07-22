"""Buyer-side payables: bills table (43B(h) / §15 compliance mirror)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column(
            "counterparty_id",
            sa.String(36),
            sa.ForeignKey("counterparties.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_paise", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="open", index=True),
        sa.Column("acceptance_date", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("bills")
