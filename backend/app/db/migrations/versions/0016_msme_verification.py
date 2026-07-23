"""counterparties Udyam verification columns (F4 vendor verify)

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "counterparties", sa.Column("msme_verified_category", sa.String(10), nullable=True)
    )
    op.add_column(
        "counterparties", sa.Column("msme_verified_urn", sa.String(25), nullable=True)
    )
    op.add_column(
        "counterparties",
        sa.Column("msme_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("counterparties", "msme_verified_at")
    op.drop_column("counterparties", "msme_verified_urn")
    op.drop_column("counterparties", "msme_verified_category")
