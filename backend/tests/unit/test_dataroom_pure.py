from app.services.dataroom import WEIGHTS, compute_score


def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100


def test_perfect_books_score_100():
    assert compute_score({k: 1.0 for k in WEIGHTS})["score"] == 100


def test_broken_chain_costs_its_full_weight():
    perfect = {k: 1.0 for k in WEIGHTS}
    broken = {**perfect, "audit_integrity": 0.0}
    assert compute_score(broken)["score"] == 100 - WEIGHTS["audit_integrity"]


def test_ratios_clamped_and_components_published():
    result = compute_score({"reconciliation": 1.7, "categorization": -0.5})
    assert result["components"]["reconciliation"]["ratio"] == 1.0
    assert result["components"]["categorization"]["ratio"] == 0.0
    assert set(result["components"]) == set(WEIGHTS)
