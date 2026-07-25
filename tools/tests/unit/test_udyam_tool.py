"""Udyam tool tests — fixture register lookups, case-normalized URNs."""

from findesk_tools.udyam import SandboxUdyamProvider


def test_verify_known_urn_returns_category():
    v = SandboxUdyamProvider().verify(urn="UDYAM-TN-02-0001234")
    assert v.found is True
    assert v.category == "micro"
    assert v.enterprise_name == "Sundaram Packaging"
    assert v.as_of == "2026-04-01"


def test_verify_medium_drift_case():
    # the seed tags Kaveri as small; the register says medium — drift the
    # payables shield must surface (43B(h) covers micro & small only)
    v = SandboxUdyamProvider().verify(urn="udyam-ka-05-0567890")  # case-insensitive
    assert v.found is True
    assert v.category == "medium"


def test_verify_unknown_urn_found_false():
    v = SandboxUdyamProvider().verify(urn="UDYAM-MH-99-9999999")
    assert v.found is False
    assert v.category is None
