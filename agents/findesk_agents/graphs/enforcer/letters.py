"""B2 enforcement artifacts — deterministic templates around fixed ladder states.

The agent never chooses an escalation step (the ladder is engine territory)
and never files anything. These templates *prepare*: an Act-referencing
demand letter at the ``act_letter`` rung, and a Samadhaan filing-preparation
summary at ``samadhaan_prep``. Both carry explicit review-with-your-CA
framing — computations and documents only, never legal advice.
"""

from __future__ import annotations

from typing import Any

from findesk_shared import format_inr

CA_NOTICE = (
    "Prepared by FinDesk under MSME Act framing for review with your CA — "
    "this is a computation and draft, not legal advice, and nothing has been filed."
)


def act_letter(
    *,
    sender_name: str,
    client_name: str,
    invoice: dict[str, Any],  # {number, amount_paise}
    clock: dict[str, Any],  # snapshot from the statutory engine
) -> dict[str, str]:
    amount = format_inr(invoice["amount_paise"])
    interest = format_inr(clock["accrued_interest_paise"])
    total = format_inr(invoice["amount_paise"] + clock["accrued_interest_paise"])
    rate = clock["annual_rate_bps"] / 100
    due = clock["statutory_due_date"][:10]

    subject = (
        f"Notice under MSMED Act 2006: invoice {invoice['number']} — "
        f"{clock['overdue_days']} days past statutory due date"
    )
    body = "\n\n".join(
        [
            f"Dear {client_name} team,",
            (
                f"Invoice {invoice['number']} for {amount} remains unpaid. Under Section 15 "
                f"of the Micro, Small and Medium Enterprises Development Act, 2006, payment "
                f"was due no later than {due} (45 days from acceptance); it is now "
                f"{clock['overdue_days']} days past that statutory date."
            ),
            (
                f"Under Section 16 of the Act, interest accrues on the unpaid amount at "
                f"{rate:g}% per annum (three times the RBI bank rate), compounded with "
                f"monthly rests. As of today this amounts to {interest}, bringing the "
                f"total payable to {total}."
            ),
            (
                "We value our working relationship and would prefer to resolve this "
                "directly. Please arrange payment within 7 days, or contact us "
                "immediately if there is any dispute regarding the invoice."
            ),
            f"Sincerely,\n{sender_name}",
            f"---\n{CA_NOTICE}",
        ]
    )
    return {"subject": subject, "body_md": body}


def samadhaan_prep(
    *,
    tenant_name: str,
    client_name: str,
    invoice: dict[str, Any],
    clock: dict[str, Any],
) -> dict[str, str]:
    amount = format_inr(invoice["amount_paise"])
    interest = format_inr(clock["accrued_interest_paise"])
    body = "\n".join(
        [
            "# MSME Samadhaan — filing preparation summary",
            "",
            f"- **Supplier (applicant)**: {tenant_name}",
            f"- **Buyer (respondent)**: {client_name}",
            f"- **Invoice**: {invoice['number']} for {amount}",
            f"- **Acceptance date (day zero)**: {clock['acceptance_date'][:10]}",
            f"- **Statutory due date (§15, 45 days)**: {clock['statutory_due_date'][:10]}",
            f"- **Days past statutory due**: {clock['overdue_days']}",
            (
                f"- **Interest accrued (§16, {clock['annual_rate_bps'] / 100:g}% p.a., "
                f"monthly rests)**: {interest}"
            ),
            f"- **Total claim**: "
            f"{format_inr(invoice['amount_paise'] + clock['accrued_interest_paise'])}",
            "",
            "## Next steps (human)",
            "1. Review the computation and supporting evidence with your CA.",
            "2. Gather: invoice copy, delivery/acceptance proof, ledger extract "
            "(FinDesk Why-trail export), prior reminders sent.",
            "3. If proceeding, file on the MSME Samadhaan portal — FinDesk does not file.",
            "",
            f"> {CA_NOTICE}",
        ]
    )
    return {"title": f"Samadhaan prep — {invoice['number']}", "body_md": body}
