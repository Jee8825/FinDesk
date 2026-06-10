import pytest

from app.services.reports import aging_bucket, period_bounds


def test_period_bounds_normal_and_december():
    start, end = period_bounds("2026-04")
    assert start.isoformat().startswith("2026-04-01")
    assert end.isoformat().startswith("2026-05-01")
    start, end = period_bounds("2026-12")
    assert end.isoformat().startswith("2027-01-01")


def test_period_bounds_rejects_garbage():
    with pytest.raises(ValueError):
        period_bounds("2026-13")
    with pytest.raises(ValueError):
        period_bounds("not-a-period")


def test_aging_buckets():
    assert aging_bucket(0) == "0–30"
    assert aging_bucket(30) == "0–30"
    assert aging_bucket(31) == "31–60"
    assert aging_bucket(60) == "31–60"
    assert aging_bucket(61) == "61+"
    assert aging_bucket(400) == "61+"
