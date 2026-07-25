"""tally@v1 gateway — the contract surface over the HTTP-XML transport.

Transport is injectable: production uses the stdlib urllib POST against a
running TallyPrime (``http://localhost:9000`` unless remapped); tests inject a
callable returning fixture XML — no live calls in CI (tools/CLAUDE.md rule 7).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from findesk_tools.tally import envelopes
from findesk_tools.tally.schemas import (
    BillRef,
    BillsResult,
    ChartResult,
    PushReceipt,
    PushRefused,
    Source,
    ToolError,
    VoucherDraft,
)

Transport = Callable[[str, str], str]  # (url, request_xml) -> response_xml

DEFAULT_GATEWAY_URL = "http://localhost:9000"


def _urllib_transport(url: str, request_xml: str) -> str:
    req = urllib.request.Request(  # noqa: S310 — operator-configured gateway URL
        url, data=request_xml.encode("utf-8"), method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ToolError("tally.unreachable", f"gateway unreachable: {exc}", retryable=True) from exc


def _tally_date(iso: str) -> str:
    """``YYYY-MM-DD`` → Tally's ``YYYYMMDD``."""
    return iso.replace("-", "")


class TallyGateway:
    name = "tally"

    def __init__(
        self,
        base_url: str = DEFAULT_GATEWAY_URL,
        *,
        company: str | None = None,
        transport: Transport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/")
        self._company = company
        self._transport = transport or _urllib_transport

    # ---------------------------------------------------------------- reads --

    def list_invoices(self, from_date: str, to_date: str) -> BillsResult:
        """Outstanding receivables (Bills Receivable) — ISO dates in, contract out."""
        xml = self._transport(
            self._url,
            envelopes.bills_receivable_request(
                _tally_date(from_date), _tally_date(to_date), self._company
            ),
        )
        return self._bills_result(xml, from_date, to_date)

    def list_bills(self, from_date: str, to_date: str) -> BillsResult:
        """Outstanding payables (Bills Payable) — the 43B(h) exposure source."""
        xml = self._transport(
            self._url,
            envelopes.bills_payable_request(
                _tally_date(from_date), _tally_date(to_date), self._company
            ),
        )
        return self._bills_result(xml, from_date, to_date)

    def get_chart_of_accounts(self) -> ChartResult:
        xml = self._transport(self._url, envelopes.ledgers_request(self._company))
        return ChartResult(accounts=envelopes.parse_ledgers(xml), company=self._company)

    # --------------------------------------------------------------- writes --

    def push_voucher(self, draft: VoucherDraft, *, approval_token: str | None) -> PushReceipt:
        if not approval_token:
            raise PushRefused()
        entries = [
            (e.ledger, Decimal(e.amount_paise) / 100, e.direction) for e in draft.ledger_entries
        ]
        xml = self._transport(
            self._url,
            envelopes.import_voucher_request(
                voucher_type=draft.voucher_type,
                date=draft.date.strftime("%Y%m%d"),
                narration=draft.narration,
                entries=entries,
                company=self._company,
            ),
        )
        outcome = envelopes.parse_import_response(xml)
        return PushReceipt(
            external_id=outcome["external_id"],
            created=outcome["created"],
            altered=outcome["altered"],
            approval_token=approval_token,
        )

    # -------------------------------------------------------------- helpers --

    def _bills_result(self, xml: str, from_date: str, to_date: str) -> BillsResult:
        fetched_at = datetime.now(UTC)
        bills: list[BillRef] = []
        for row in envelopes.parse_bills(xml, fetched_at=fetched_at):
            fallback_ref = f"tally:{row['party']}:{row['bill_date_raw']}"
            outstanding = envelopes.rupees_to_paise_abs(row.get("outstanding_raw", "0"))
            # BILLOP (opening amount) is absent from some Tally builds' exports;
            # outstanding is then the best available original-amount signal.
            amount = (
                envelopes.rupees_to_paise_abs(row["amount_raw"])
                if row.get("amount_raw")
                else outstanding
            )
            if amount <= 0:
                continue  # fully-settled artifacts carry no information here
            bills.append(
                BillRef(
                    external_ref=row["external_ref"] or fallback_ref,
                    party=row["party"],
                    bill_date=envelopes.parse_tally_date(row["bill_date_raw"]),
                    due_date=(
                        envelopes.parse_tally_date(row["due_date_raw"])
                        if row.get("due_date_raw")
                        else None
                    ),
                    amount_paise=amount,
                    outstanding_paise=outstanding,
                    source=Source(external_id=row["external_ref"] or "-", fetched_at=fetched_at),
                )
            )
        return BillsResult(bills=bills, period=f"{from_date}..{to_date}", company=self._company)
