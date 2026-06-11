"""Enforcement template tests — figures must match the engine to the paisa."""

from findesk_agents.graphs.enforcer.letters import CA_NOTICE, act_letter, samadhaan_prep

CLOCK = {
    "acceptance_date": "2026-03-26T00:00:00+00:00",
    "statutory_due_date": "2026-05-10T00:00:00+00:00",
    "overdue_days": 32,
    "accrued_interest_paise": 108_169,
    "annual_rate_bps": 2025,
}
INVOICE = {"number": "INV-2026-049", "amount_paise": 6_000_000}


def test_act_letter_cites_sections_and_exact_figures():
    letter = act_letter(
        sender_name="Accounts, Demo Trading Co",
        client_name="Blue Tokai Coffee Pvt Ltd",
        invoice=INVOICE,
        clock=CLOCK,
    )
    assert "Section 15" in letter["body_md"]
    assert "Section 16" in letter["body_md"]
    assert "₹60,000.00" in letter["body_md"]
    assert "₹1,081.69" in letter["body_md"]  # engine interest, verbatim
    assert "₹61,081.69" in letter["body_md"]  # principal + interest
    assert "20.25% per annum" in letter["body_md"]
    assert CA_NOTICE in letter["body_md"]
    assert "32 days past" in letter["subject"]


def test_samadhaan_prep_is_preparation_not_filing():
    doc = samadhaan_prep(
        tenant_name="Demo Trading Co",
        client_name="Blue Tokai Coffee Pvt Ltd",
        invoice=INVOICE,
        clock=CLOCK,
    )
    assert "FinDesk does not file" in doc["body_md"]
    assert "2026-05-10" in doc["body_md"]
    assert CA_NOTICE in doc["body_md"]
