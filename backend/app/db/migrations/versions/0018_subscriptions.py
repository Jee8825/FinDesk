"""subscriptions table + tenants.leak_mode (LeakRadar)

One row per recurring vendor series, upserted by (tenant_id, vendor_slug) so a
rescan refreshes rather than duplicates. `usage` is deliberately NOT recomputed
by a scan — it is the one field a human owns, and it is what licenses counting a
whole subscription as recoverable.

`tenants.leak_mode` selects the exclusion list: a business book must never rank
payroll as a leak, a personal one must never rank an EMI.

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("leak_mode", sa.String(10), nullable=False, server_default="business"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("vendor_slug", sa.String(120), nullable=False),
        sa.Column("vendor_label", sa.String(120), nullable=False),
        sa.Column("category_code", sa.String(40), nullable=True),
        sa.Column("cadence", sa.String(14), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("periods_per_year", sa.Integer(), nullable=True),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_expected", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("latest_amount_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("run_rate_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("drift_kind", sa.String(20), nullable=True),
        sa.Column("drift_paise_per_year", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duplicate_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("leak_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_components", sa.JSON(), nullable=False),
        sa.Column(
            "recoverable_paise_per_year", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("reason", sa.String(400), nullable=False, server_default=""),
        sa.Column("recommended_action", sa.String(300), nullable=False, server_default=""),
        sa.Column("narrative", sa.String(1000), nullable=True),
        sa.Column("usage", sa.String(10), nullable=True),
        sa.Column("usage_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "vendor_slug", name="uq_subscription_tenant_vendor"),
    )
    op.create_index("ix_subscriptions_tenant_id", "subscriptions", ["tenant_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    op.create_index("ix_subscriptions_cadence", "subscriptions", ["cadence"])
    op.create_index("ix_subscriptions_leak_score", "subscriptions", ["leak_score"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_leak_score", table_name="subscriptions")
    op.drop_index("ix_subscriptions_cadence", table_name="subscriptions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_tenant_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_column("tenants", "leak_mode")
