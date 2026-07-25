"""subscriptions.draft — LLM-written cancel/renegotiate email, stored not live

Backend rule 1 forbids LLM calls in request handlers, so the draft is produced
by the subscription_scan graph and persisted here. POST /leaks/{id}/action then
queues an approval using the stored draft; the send itself stays token-gated in
decide_approval like every other outbound message.

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("draft", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "draft")
