"""B2 enforcer: track the last escalation level acted upon per clock

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "statutory_clocks",
        sa.Column("last_enforced_level", sa.String(20), nullable=False, server_default="none"),
    )


def downgrade() -> None:
    op.drop_column("statutory_clocks", "last_enforced_level")
