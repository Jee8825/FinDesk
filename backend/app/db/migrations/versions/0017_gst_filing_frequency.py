"""tenants.gst_filing_frequency (N3 IMS deemed-accept clock)

Drives how much grace an un-actioned IMS record gets before the portal deems
it accepted: one month for a monthly filer, one quarter under QRMP. Defaults to
"monthly" — the shorter window, so an unconfigured tenant is warned early
rather than late.

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "gst_filing_frequency",
            sa.String(10),
            nullable=False,
            server_default="monthly",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "gst_filing_frequency")
