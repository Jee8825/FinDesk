"""A7 drafting unit tests — tone calibration from remembered behavior."""

from findesk_agents.graphs.collections.drafting import behavior_profile, compose_draft

INVOICE = {
    "id": "i1",
    "number": "INV-2026-052",
    "amount_paise": 15_000_000,
    "due_date": "2026-04-29T00:00:00+00:00",
}
CLIENT = {"id": "p1", "name": "Subko Specialty"}


def test_behavior_profile_parses_late_days():
    memories = [
        {"content": "Invoice INV-1 (₹95,000.00) was paid 9 days late relative to its due date."},
        {"content": "Invoice INV-2 (₹45,000.00) was paid 12 days late relative to its due date."},
        {"content": "This client deducts 2% TDS on payments."},
    ]
    profile = behavior_profile(memories)
    assert profile == {"observations": 2, "avg_days_late": 10.5, "reliable": True}


def test_reliable_client_recently_overdue_gets_gentle_tone():
    profile = {"observations": 3, "avg_days_late": 9.0, "reliable": True}
    draft = compose_draft(INVOICE, CLIENT, profile, days_overdue=12, sender_name="Accounts")
    assert draft["tone"] == "gentle"
    assert "Friendly" in draft["subject"]
    assert "₹1,50,000.00" in draft["body_md"]


def test_unknown_client_gets_neutral_tone():
    draft = compose_draft(
        INVOICE, CLIENT, behavior_profile([]), days_overdue=12, sender_name="Accounts"
    )
    assert draft["tone"] == "neutral"


def test_heavily_overdue_gets_firm_tone_regardless_of_history():
    profile = {"observations": 3, "avg_days_late": 9.0, "reliable": True}
    draft = compose_draft(INVOICE, CLIENT, profile, days_overdue=43, sender_name="Accounts")
    assert draft["tone"] == "firm"
    assert "43 days" in draft["subject"]
    assert draft["thread_ref"] == "invoice:i1"
