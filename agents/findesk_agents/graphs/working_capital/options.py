"""B4 option builder — pure: receivables in, ranked costed actions out.

Two action kinds in this slice (re-timing payables lands with bills/AP):

* **treds** — discount a not-yet-due receivable on TReDS. Tenor = days until
  the client's *predicted* payment (B1), so the cost is precisely the price
  of moving that arrival to today. Skipped when tenor is tiny — paying to
  accelerate money that's a few days away is bad advice.
* **collect** — push an overdue receivable through collections. No fee, but
  certainty depends on the client; the card says so instead of pretending.

Ranking: cost per rupee unlocked, ascending (collect's zero fee naturally
ranks first), then unlock size. Every option is recommend-only — execution
is the approval queue's job.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

MIN_TREDS_TENOR_DAYS = 7
DEFAULT_PAY_DELAY_DAYS = 7


def build_options(
    *,
    now: datetime,
    open_invoices: list[dict[str, Any]],  # {id, number, client, client_id, amount_paise, due_date}
    avg_late_by_client: dict[str, float],
    quote_fn,  # (invoice_ref, amount_paise, tenor_days) -> TredsQuote-shaped dict
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for inv in open_invoices:
        due = datetime.fromisoformat(inv["due_date"])
        avg_late = avg_late_by_client.get(inv["client_id"], DEFAULT_PAY_DELAY_DAYS)
        predicted = due + timedelta(days=avg_late)
        days_to_cash = (predicted - now).days

        if days_to_cash >= MIN_TREDS_TENOR_DAYS:
            quote = quote_fn(
                invoice_ref=inv["number"],
                amount_paise=inv["amount_paise"],
                tenor_days=days_to_cash,
            )
            options.append(
                {
                    "kind": "treds",
                    "invoice_id": inv["id"],
                    "invoice_number": inv["number"],
                    "client": inv["client"],
                    "unlock_paise": quote["unlock_paise"],
                    "cost_paise": quote["cost_paise"],
                    "detail": {
                        "quote": quote,
                        "days_to_cash_without_action": days_to_cash,
                        "predicted_payment": predicted.date().isoformat(),
                    },
                }
            )
        elif (now - due).days > 0:
            overdue = (now - due).days
            options.append(
                {
                    "kind": "collect",
                    "invoice_id": inv["id"],
                    "invoice_number": inv["number"],
                    "client": inv["client"],
                    "unlock_paise": inv["amount_paise"],
                    "cost_paise": 0,
                    "detail": {
                        "days_overdue": overdue,
                        "avg_days_late": avg_late_by_client.get(inv["client_id"]),
                        "note": (
                            "No fee, but timing depends on the client — pair with the "
                            "collections chaser and the 45-day ladder."
                        ),
                    },
                }
            )

    options.sort(key=lambda o: (o["cost_paise"] / max(o["unlock_paise"], 1), -o["unlock_paise"]))
    for rank, option in enumerate(options, start=1):
        option["rank"] = rank
    return options
