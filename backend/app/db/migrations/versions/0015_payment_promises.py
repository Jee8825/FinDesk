"""payment_promises — PTP capture + settle outcomes (F3 outcome loop)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_promises",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column(
            "invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), nullable=False, index=True
        ),
        sa.Column("promised_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_paise", sa.BigInteger, nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="open", index=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("note", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("payment_promises")
