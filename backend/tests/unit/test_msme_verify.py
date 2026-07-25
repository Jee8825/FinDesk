"""F4 scope logic — verified category beats the tag; drift is the flip."""

from app.services.payables import effective_mse


def test_no_verification_falls_back_to_self_declared():
    assert effective_mse("micro", None) == (True, "self_declared", False)
    assert effective_mse("", None) == (False, "self_declared", False)
    assert effective_mse("medium", None) == (False, "self_declared", False)


def test_verified_mse_confirms_tag_no_drift():
    assert effective_mse("micro", "micro") == (True, "verified", False)
    # micro→small recategorization stays in scope: not a drift alert
    assert effective_mse("micro", "small") == (True, "verified", False)


def test_verified_medium_drifts_out_of_43bh():
    # the Kaveri case: tagged small, register says medium — out of scope
    assert effective_mse("small", "medium") == (False, "verified", True)


def test_verified_mse_on_untagged_vendor_drifts_in():
    # untagged vendor verifies micro: enters scope the tag missed
    assert effective_mse("", "micro") == (True, "verified", True)


def test_verified_medium_on_untagged_no_drift():
    assert effective_mse("", "medium") == (False, "verified", False)
