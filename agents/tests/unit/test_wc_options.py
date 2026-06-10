"""B4 option-builder tests — pure logic with a stub quote function."""

from datetime import UTC, datetime

from findesk_agents.graphs.working_capital.options import build_options

NOW = datetime(2026, 6, 15, tzinfo=UTC)


def _quote(invoice_ref, amount_paise, tenor_days):
    cost = round(amount_paise * 0.18 * tenor_days / 365)
    return {
        "invoice_ref": invoice_ref,
        "amount_paise": amount_paise,
        "tenor_days": tenor_days,
        "cost_paise": cost,
        "unlock_paise": amount_paise - cost,
        "discount_rate_bps_annual": 1800,
        "platform": "stub",
    }


def _inv(id="i1", number="INV-1", client_id="c1", amount=40_000_000, due="2026-07-05"):
    return {
        "id": id,
        "number": number,
        "client": "Subko",
        "client_id": client_id,
        "amount_paise": amount,
        "due_date": f"{due}T00:00:00+00:00",
    }


def test_future_receivable_gets_treds_option_on_predicted_tenor():
    options = build_options(
        now=NOW,
        open_invoices=[_inv()],
        avg_late_by_client={"c1": 18.0},
        quote_fn=_quote,
    )
    assert len(options) == 1
    o = options[0]
    assert o["kind"] == "treds"
    # due 07-05 + 18d late = 07-23 → 38 days from 06-15
    assert o["detail"]["quote"]["tenor_days"] == 38
    assert o["cost_paise"] == round(40_000_000 * 0.18 * 38 / 365)
    assert o["unlock_paise"] == 40_000_000 - o["cost_paise"]


def test_overdue_receivable_gets_collect_option():
    options = build_options(
        now=NOW,
        open_invoices=[_inv(due="2026-05-01")],
        avg_late_by_client={},
        quote_fn=_quote,
    )
    assert options[0]["kind"] == "collect"
    assert options[0]["cost_paise"] == 0
    assert options[0]["detail"]["days_overdue"] == 45


def test_imminent_money_gets_no_treds_option():
    # due tomorrow, client pays on time-ish → tenor < 7 days → no option at all
    options = build_options(
        now=NOW,
        open_invoices=[_inv(due="2026-06-16")],
        avg_late_by_client={"c1": 2.0},
        quote_fn=_quote,
    )
    assert options == []


def test_ranking_collect_first_then_cheapest_treds():
    invoices = [
        _inv(id="i1", number="T-BIG", amount=40_000_000, due="2026-07-05"),
        _inv(id="i2", number="T-LONG", client_id="c2", amount=40_000_000, due="2026-08-20"),
        _inv(id="i3", number="C-OVERDUE", amount=10_000_000, due="2026-05-01"),
    ]
    options = build_options(
        now=NOW,
        open_invoices=invoices,
        avg_late_by_client={"c1": 5.0, "c2": 5.0},
        quote_fn=_quote,
    )
    kinds = [(o["rank"], o["kind"], o["invoice_number"]) for o in options]
    assert kinds[0] == (1, "collect", "C-OVERDUE")
    assert kinds[1][2] == "T-BIG"  # shorter tenor = cheaper per rupee
    assert kinds[2][2] == "T-LONG"
