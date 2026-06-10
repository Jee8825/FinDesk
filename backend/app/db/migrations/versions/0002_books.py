"""books: counterparties, bank accounts/transactions, invoices, matches,
ledger entries, audit log, documents

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _common():
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "counterparties",
        *_common(),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("gstin", sa.String(15), nullable=True),
        sa.Column("msme_status", sa.String(20), nullable=True),
        sa.Column("contacts", sa.JSON(), nullable=False),
    )
    op.create_table(
        "bank_accounts",
        *_common(),
        sa.Column("bank", sa.String(100), nullable=False),
        sa.Column("account_ref", sa.String(50), nullable=False),
        sa.Column("source", sa.String(10), nullable=False, server_default="upload"),
    )
    op.create_table(
        "bank_transactions",
        *_common(),
        sa.Column(
            "bank_account_id",
            sa.String(36),
            sa.ForeignKey("bank_accounts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("external_ref", sa.String(100), nullable=False),
        sa.Column("value_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("direction", sa.String(2), nullable=False),
        sa.Column("narration", sa.String(500), nullable=False),
        sa.Column("counterparty_hint", sa.String(200), nullable=True),
        sa.Column("dedupe_hash", sa.String(64), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column(
            "match_status", sa.String(12), nullable=False, server_default="unmatched", index=True
        ),
        sa.UniqueConstraint("bank_account_id", "dedupe_hash"),
    )
    op.create_table(
        "invoices",
        *_common(),
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
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="open", index=True),
    )
    op.create_table(
        "matches",
        *_common(),
        sa.Column(
            "bank_transaction_id",
            sa.String(36),
            sa.ForeignKey("bank_transactions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("target_kind", sa.String(10), nullable=False, server_default="invoice"),
        sa.Column("target_id", sa.String(36), nullable=False, index=True),
        sa.Column("kind", sa.String(15), nullable=False, server_default="full"),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("matched_by", sa.String(10), nullable=False, server_default="agent"),
        sa.Column("critic_verdict", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="proposed"),
    )
    op.create_table(
        "ledger_entries",
        *_common(),
        sa.Column("entry_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lines", sa.JSON(), nullable=False),
        sa.Column("origin", sa.JSON(), nullable=False),
    )
    op.create_table(
        "audit_log",
        *_common(),
        sa.Column("actor", sa.JSON(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("entity_ref", sa.String(80), nullable=False, index=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("row_hash", sa.String(64), nullable=False),
    )
    op.create_table(
        "documents",
        *_common(),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "documents",
        "audit_log",
        "ledger_entries",
        "matches",
        "invoices",
        "bank_transactions",
        "bank_accounts",
        "counterparties",
    ):
        op.drop_table(table)
