"""audit hardening: hot-path indexes + committed-match uniqueness guard

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # hot list/filter paths
    op.create_index(
        "ix_bank_txns_tenant_status", "bank_transactions", ["tenant_id", "match_status"]
    )
    op.create_index("ix_invoices_tenant_status", "invoices", ["tenant_id", "status"])
    # collections cooldown + why-trail scans
    op.create_index(
        "ix_audit_tenant_action_created", "audit_log", ["tenant_id", "action", "created_at"]
    )
    # the hard double-commit guarantee: at most one committed match per invoice
    # (the service-level guarded UPDATEs are the fast path; this is the floor)
    op.create_index(
        "uq_committed_match_target",
        "matches",
        ["target_id"],
        unique=True,
        postgresql_where=sa.text("status = 'committed'"),
    )


def downgrade() -> None:
    op.drop_index("uq_committed_match_target", table_name="matches")
    op.drop_index("ix_audit_tenant_action_created", table_name="audit_log")
    op.drop_index("ix_invoices_tenant_status", table_name="invoices")
    op.drop_index("ix_bank_txns_tenant_status", table_name="bank_transactions")
