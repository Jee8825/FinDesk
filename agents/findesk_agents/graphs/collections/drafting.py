"""A7 draft composition — pure, behavior-aware, escalation-laddered.

Tone is calibrated from remembered payment behavior (B1 feedstock):
* a client who reliably pays (just late) gets a gentle nudge;
* a worsening or heavily-overdue client gets a firmer, dated reminder.

The wording escalates with days overdue, but the *ladder itself* is fixed
state machine territory (statutory steps land with B2) — the agent chooses
words, never steps. Drafts are recommend-only; sending is human-gated.
"""

from __future__ import annotations

from typing import Any

from findesk_shared import format_inr, parse_late_days

GENTLE_MAX_OVERDUE = 30


def behavior_profile(memories: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize remembered payment behavior for one client."""
    lates = parse_late_days([m.get("content", "") for m in memories])
    return {
        "observations": len(lates),
        "avg_days_late": round(sum(lates) / len(lates), 1) if lates else None,
        "reliable": bool(lates) and max(lates) <= 21,
    }


def compose_draft(
    invoice: dict[str, Any],
    client: dict[str, Any],
    profile: dict[str, Any],
    *,
    days_overdue: int,
    sender_name: str,
) -> dict[str, Any]:
    amount_str = format_inr(invoice["amount_paise"])  # lakh/crore grouping
    number = invoice["number"]
    due = invoice["due_date"][:10]
    name = client["name"]

    if days_overdue <= GENTLE_MAX_OVERDUE and profile.get("reliable", False):
        tone = "gentle"
        subject = f"Friendly reminder: invoice {number}"
        opener = (
            f"Hope things are going well. A quick note that invoice {number} "
            f"for {amount_str} was due on {due}."
        )
        closer = (
            "You've always been prompt with us, so this is just a nudge — "
            "please ignore if payment is already on its way."
        )
    elif days_overdue <= GENTLE_MAX_OVERDUE:
        tone = "neutral"
        subject = f"Payment reminder: invoice {number} ({amount_str})"
        opener = (
            f"This is a reminder that invoice {number} for {amount_str} "
            f"was due on {due} and is now {days_overdue} days overdue."
        )
        closer = "Could you share an expected payment date? Happy to resend the invoice."
    else:
        tone = "firm"
        subject = f"Overdue notice: invoice {number} — {days_overdue} days past due"
        opener = (
            f"Invoice {number} for {amount_str} was due on {due} and remains "
            f"unpaid after {days_overdue} days."
        )
        closer = (
            "Please arrange payment this week or let us know of any issue with "
            "the invoice. We'd like to settle this without further escalation."
        )

    body = "\n\n".join(
        [
            f"Dear {name} team,",
            opener,
            closer,
            f"Best regards,\n{sender_name}",
        ]
    )
    return {
        "tone": tone,
        "subject": subject,
        "body_md": body,
        "thread_ref": f"invoice:{invoice['id']}",
    }
