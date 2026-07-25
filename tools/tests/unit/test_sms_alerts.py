"""SMS debit-alert parsing — real Indian bank templates.

An inbox is mostly noise, so the important properties are what the parser
IGNORES: OTPs, balance summaries and credits must never become debit rows.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from findesk_tools.sms_alerts import parse_alert, parse_inbox

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "findesk_tools/sms_alerts/fixtures/inbox.json"
)
NOW = datetime(2026, 7, 25, tzinfo=UTC)


def test_hdfc_debit_alert():
    p = parse_alert(
        "Rs.649.00 debited from a/c XX4412 on 04-07-2026 to NETFLIX PREMIUM.",
        bank="HDFCBK",
    )
    assert p is not None
    assert p.amount_paise == 64_900
    assert p.narration == "NETFLIX PREMIUM"
    assert p.account_ref == "4412"
    assert p.value_date.date() == datetime(2026, 7, 4, tzinfo=UTC).date()


def test_icici_card_spend_with_slash_date_and_trailing_balance():
    p = parse_alert(
        "INR 2,999.00 spent on ICICI Bank Card XX7781 on 23/07/2026 at GOLD GYM "
        "ELITE. Avl bal INR 41,220.15"
    )
    assert p is not None
    assert p.amount_paise == 299_900
    assert p.narration == "GOLD GYM ELITE", "the balance tail must not leak in"


def test_sbi_alert_with_month_name_date():
    p = parse_alert(
        "Your a/c no. XX9930 is debited by Rs.199.00 on 07-Jul-2026 towards "
        "SPOTIFY FAMILY -SBI"
    )
    assert p is not None
    assert p.amount_paise == 19_900
    assert p.value_date.date() == datetime(2026, 7, 7, tzinfo=UTC).date()


def test_reference_tail_is_stripped_from_the_merchant():
    p = parse_alert(
        "Rs 1,499.00 debited A/c no. XX1188 07-07-2026 for AMAZON PRIME "
        "MEMBERSHIP UPI/Ref 421887"
    )
    assert p is not None
    assert p.narration == "AMAZON PRIME MEMBERSHIP"


def test_an_otp_is_not_a_transaction():
    assert (
        parse_alert("OTP 884213 is your one time password to authorise a txn of Rs.500.")
        is None
    )


def test_a_credit_is_not_a_leak():
    assert (
        parse_alert("INR 85,000.00 credited to a/c XX7781 on 02-07-2026 from ACME CORP.")
        is None
    )


def test_a_balance_summary_is_not_a_transaction():
    assert (
        parse_alert("Available balance is Rs.41,220.15 in a/c XX4412 as on 24-07-2026")
        is None
    )


def test_missing_merchant_is_skipped_rather_than_guessed():
    assert parse_alert("Rs.500.00 debited from a/c XX4412 on 04-07-2026.") is None


def test_undated_alert_falls_back_to_received_time():
    p = parse_alert("Rs.99.00 debited to SWIGGY ONE", received_at=NOW)
    assert p is not None and p.value_date == NOW


def test_row_shape_matches_the_statement_parser():
    p = parse_alert(
        "Rs.210.00 deducted from Kotak a/c XX2210 on 15-07-2026 to GOOGLE ONE",
        bank="KOTAKB",
    )
    row = p.as_row()
    assert set(row) >= {"value_date", "amount_paise", "direction", "narration", "source"}
    assert row["direction"] == "dr"
    assert row["source"] == {"kind": "sms_alert", "bank": "KOTAKB"}


def test_inbox_batch_reports_what_it_skipped():
    out = parse_inbox(json.loads(FIXTURE.read_text()), received_at=NOW)
    assert out["parsed"] == 5, "5 debits in the fixture"
    assert out["skipped"] == 3, "otp + credit + balance summary"
    assert all(r["direction"] == "dr" for r in out["rows"])
