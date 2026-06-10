"""B3: versioned forecast runs

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "forecasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("horizon_weeks", sa.Integer(), nullable=False),
        sa.Column("opening_balance_paise", sa.BigInteger(), nullable=False),
        sa.Column("weekly_outflow_paise", sa.BigInteger(), nullable=False),
        sa.Column("outflow_basis", sa.JSON(), nullable=False),
        sa.Column("gap", sa.JSON(), nullable=True),
        sa.Column("narrative", sa.JSON(), nullable=False),
    )
    op.create_table(
        "forecast_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column(
            "forecast_id",
            sa.String(36),
            sa.ForeignKey("forecasts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("scenario", sa.String(10), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.String(10), nullable=False),
        sa.Column("inflow_paise", sa.BigInteger(), nullable=False),
        sa.Column("outflow_paise", sa.BigInteger(), nullable=False),
        sa.Column("closing_paise", sa.BigInteger(), nullable=False),
        sa.Column("drivers", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("forecast_lines")
    op.drop_table("forecasts")
