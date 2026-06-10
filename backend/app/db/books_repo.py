"""Books repositories — all Phase-1 SQL for transactions/invoices/matches/audit."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLog,
    BankAccount,
    BankTransaction,
    Counterparty,
    Document,
    Invoice,
    LedgerEntry,
    Match,
)


class BooksRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- documents -------------------------------------------------------
    async def add_document(self, doc: Document) -> None:
        self.session.add(doc)

    async def document(self, document_id: str, tenant_id: str) -> Document | None:
        return await self.session.scalar(
            select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        )

    # ---- accounts / counterparties ---------------------------------------
    async def default_bank_account(self, tenant_id: str) -> BankAccount | None:
        return await self.session.scalar(
            select(BankAccount).where(BankAccount.tenant_id == tenant_id).limit(1)
        )

    async def counterparties(self, tenant_id: str) -> list[Counterparty]:
        rows = await self.session.scalars(
            select(Counterparty).where(Counterparty.tenant_id == tenant_id)
        )
        return list(rows)

    # ---- transactions ------------------------------------------------------
    async def insert_transactions_deduped(
        self, rows: list[dict[str, Any]]
    ) -> tuple[int, int]:
        """Insert normalized rows, skipping (account, dedupe_hash) duplicates.

        Returns (inserted, skipped).
        """
        if not rows:
            return (0, 0)
        stmt = pg_insert(BankTransaction).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["bank_account_id", "dedupe_hash"])
        result = await self.session.execute(stmt)
        inserted = result.rowcount or 0
        return (inserted, len(rows) - inserted)

    async def transactions(
        self,
        tenant_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> list[BankTransaction]:
        q = select(BankTransaction).where(BankTransaction.tenant_id == tenant_id)
        if status:
            q = q.where(BankTransaction.match_status == status)
        if cursor:
            q = q.where(BankTransaction.id < cursor)
        q = q.order_by(BankTransaction.id.desc()).limit(min(limit, 500))
        return list(await self.session.scalars(q))

    async def unmatched_transactions(self, tenant_id: str) -> list[BankTransaction]:
        return list(
            await self.session.scalars(
                select(BankTransaction).where(
                    BankTransaction.tenant_id == tenant_id,
                    BankTransaction.match_status == "unmatched",
                )
            )
        )

    async def transaction_counts(self, tenant_id: str) -> dict[str, int]:
        rows = await self.session.execute(
            select(BankTransaction.match_status, func.count())
            .where(BankTransaction.tenant_id == tenant_id)
            .group_by(BankTransaction.match_status)
        )
        return {status: count for status, count in rows}

    async def set_transaction_matched(self, txn_id: str) -> None:
        await self.session.execute(
            update(BankTransaction)
            .where(BankTransaction.id == txn_id)
            .values(match_status="matched")
        )

    # ---- invoices ----------------------------------------------------------
    async def open_invoices(self, tenant_id: str) -> list[Invoice]:
        return list(
            await self.session.scalars(
                select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.status == "open")
            )
        )

    async def invoice(self, invoice_id: str, tenant_id: str) -> Invoice | None:
        return await self.session.scalar(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        )

    async def set_invoice_paid(self, invoice_id: str) -> None:
        await self.session.execute(
            update(Invoice).where(Invoice.id == invoice_id).values(status="paid")
        )

    # ---- matches / ledger ----------------------------------------------------
    async def add_match(self, match: Match) -> None:
        self.session.add(match)

    async def match_by_id(self, match_id: str, tenant_id: str) -> Match | None:
        return await self.session.scalar(
            select(Match).where(Match.id == match_id, Match.tenant_id == tenant_id)
        )

    async def committed_match_for_target(self, target_id: str) -> Match | None:
        return await self.session.scalar(
            select(Match).where(Match.target_id == target_id, Match.status == "committed")
        )

    async def add_ledger_entry(self, entry: LedgerEntry) -> None:
        self.session.add(entry)

    # ---- audit ---------------------------------------------------------------
    async def last_audit_hash(self, tenant_id: str) -> str:
        row = await self.session.scalar(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(1)
        )
        return row.row_hash if row else "genesis"

    async def add_audit(self, entry: AuditLog) -> None:
        self.session.add(entry)

    async def audit_for_entity(self, tenant_id: str, entity_ref: str) -> list[AuditLog]:
        return list(
            await self.session.scalars(
                select(AuditLog)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.entity_ref == entity_ref)
                .order_by(AuditLog.created_at)
            )
        )
