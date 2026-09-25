from typing import Any

import pytest

from app.domain.economics import CostBreakdown
from app.domain.pricing import calculate_price


def test_pricing_quote_uses_distance_and_cargo_rate():
    costs = CostBreakdown("test", 0.62, "diesel", "l", 1.5, 80, 62, (), 0, 142)
    quote = calculate_price(10, 100, costs, 0.25)
    assert (quote.payout_eur, quote.operating_cost_eur, quote.profit_eur) == (
        470,
        142,
        328,
    )
    assert calculate_price(10, 100, costs, 0.18).payout_eur == 400
    assert (
        calculate_price(1, 100, costs, 0.18, minimum_eur_per_km=2).payout_eur
        == 420
    )
    valid = [10, 100, costs, 0.25]
    for index in (0, 1, 3):
        for invalid in (float("nan"), float("inf"), -1, True):
            values = list(valid)
            values[index] = invalid
            with pytest.raises(ValueError):
                calculate_price(*values)
    invalid_cases: Any = (
        (0, 100, costs, 0.25),
        (10, 0, costs, 0.25),
        (10, 100, None, 0.25),
    )
    for values in invalid_cases:
        with pytest.raises(ValueError):
            calculate_price(*values)
    with pytest.raises(ValueError):
        calculate_price(10, 100, costs, 0.25, minimum_eur_per_km=-1)
