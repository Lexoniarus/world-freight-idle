import pytest

from app.domain.pricing import calculate_price


def test_pricing_quote_uses_distance_and_cargo_rate():
    quote = calculate_price(10, 100, 0.62, 0.25)
    assert (quote.payout_eur, quote.operating_cost_eur, quote.profit_eur) == (
        470,
        142,
        328,
    )
    assert calculate_price(10, 100, 0.9, 0.25).operating_cost_eur == 170
    assert calculate_price(10, 100, 0.62, 0.18).payout_eur == 400
    valid = [10, 100, 0.62, 0.25]
    for index in range(4):
        for invalid in (float("nan"), float("inf"), -1, True):
            values = list(valid)
            values[index] = invalid
            with pytest.raises(ValueError):
                calculate_price(*values)
    for values in ((0, 100, 0.62, 0.25), (10, 0, 0.62, 0.25)):
        with pytest.raises(ValueError):
            calculate_price(*values)
