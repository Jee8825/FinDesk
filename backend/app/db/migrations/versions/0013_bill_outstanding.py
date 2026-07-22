"""bills.outstanding_paise — §16/43B(h) exposure runs on the unpaid portion

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bills",
        sa.Column("outstanding_paise", sa.BigInteger, nullable=True),
    )
    # backfill: everything seeded so far is fully outstanding
    op.execute("UPDATE bills SET outstanding_paise = amount_paise WHERE outstanding_paise IS NULL")
    op.alter_column("bills", "outstanding_paise", nullable=False)


def downgrade() -> None:
    op.drop_column("bills", "outstanding_paise")
