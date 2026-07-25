"""ims_records — the tenant's GST IMS queue (F1: IMS Copilot)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ims_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("record_key", sa.String(120), nullable=False),
        sa.Column("supplier_gstin", sa.String(15), nullable=False),
        sa.Column("supplier_name", sa.String(200), nullable=False),
        sa.Column("doc_type", sa.String(12), nullable=False, server_default="invoice"),
        sa.Column("doc_number", sa.String(50), nullable=False),
        sa.Column("doc_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("taxable_value_paise", sa.BigInteger, nullable=False),
        sa.Column("tax_paise", sa.BigInteger, nullable=False),
        sa.Column("total_paise", sa.BigInteger, nullable=False),
        sa.Column("state", sa.String(10), nullable=False, server_default="pending", index=True),
        sa.Column("match_tier", sa.String(20), nullable=True),
        sa.Column("matched_bill_number", sa.String(50), nullable=True),
        sa.Column("recommendation", sa.String(10), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.UniqueConstraint("tenant_id", "record_key", name="uq_ims_tenant_key"),
    )


def downgrade() -> None:
    op.drop_table("ims_records")
