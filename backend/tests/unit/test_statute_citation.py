"""MSME disallowance citation — test vectors.

A wrong section number does not throw; it just makes a CA distrust every other
figure on the page. Both acts are live during the transition, so the vectors
pin the boundary from both sides.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.statutory import (
    ITA_2025_EFFECTIVE_FROM,
    msme_disallowance_citation,
    tax_year_of,
)


@pytest.mark.parametrize(
    ("date", "expected"),
    [
        (datetime(2026, 4, 1, tzinfo=UTC), "2026-27"),
        (datetime(2026, 7, 25, tzinfo=UTC), "2026-27"),
        (datetime(2027, 3, 31, tzinfo=UTC), "2026-27"),
        (datetime(2026, 3, 31, tzinfo=UTC), "2025-26"),
        (datetime(2026, 1, 1, tzinfo=UTC), "2025-26"),
    ],
)
def test_tax_year_starts_in_april(date, expected):
    assert tax_year_of(date) == expected


def test_current_year_cites_the_2025_act():
    c = msme_disallowance_citation(datetime(2026, 7, 25, tzinfo=UTC))
    assert c["section"] == "37(2)(g)"
    assert c["act"] == "Income-tax Act 2025"
    assert c["tax_year"] == "2026-27"


def test_fy_2025_26_still_cites_43bh():
    """The year under audit until 30 Sep 2026 — citing §37(2)(g) here would be
    wrong, not merely old."""
    c = msme_disallowance_citation(datetime(2026, 3, 31, tzinfo=UTC))
    assert c["section"] == "43B(h)"
    assert c["act"] == "Income-tax Act 1961"
    assert c["tax_year"] == "2025-26"


def test_the_boundary_is_1_april_2026():
    before = msme_disallowance_citation(
        ITA_2025_EFFECTIVE_FROM.replace(month=3, day=31)
    )
    on = msme_disallowance_citation(ITA_2025_EFFECTIVE_FROM)
    assert before["section"] == "43B(h)"
    assert on["section"] == "37(2)(g)", "the 2025 Act applies FROM 1 Apr, inclusive"


def test_the_new_citation_names_its_predecessor():
    """During the transition a bare section number is ambiguous — a CA is
    working both years at once."""
    c = msme_disallowance_citation(datetime(2026, 7, 25, tzinfo=UTC))
    assert "43B(h)" in c["predecessor"]
    assert "1961" in c["predecessor"]


def test_the_old_citation_points_forward():
    c = msme_disallowance_citation(datetime(2026, 2, 1, tzinfo=UTC))
    assert "37(2)(g)" in c["note"]
    assert "1 Apr 2026" in c["note"]
