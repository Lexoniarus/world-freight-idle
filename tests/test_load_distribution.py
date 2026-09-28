"""Bounded, reproducible high-utilization shipment distribution."""

import random
import statistics

import pytest

from app.domain.market_calculations import biased_load_factor, shipment_tons


@pytest.mark.parametrize("capacity", [1.1, 2.0, 5.3, 24.2])
@pytest.mark.parametrize("lower,upper", [(0.1, 0.9), (0.5, 1), (0.8, 0.95)])
def test_load_distribution_is_bounded_biased_and_reproducible(
    capacity, lower, upper
):
    rng = random.Random(712)
    values = [
        biased_load_factor(lower, upper, rng.random()) for _ in range(20000)
    ]
    repeat = random.Random(712)
    assert values == [
        biased_load_factor(lower, upper, repeat.random()) for _ in values
    ]
    assert all(lower <= value <= upper for value in values)
    assert all(
        0.01 <= shipment_tons(capacity, value) <= capacity for value in values
    )
    normalized = [(value - lower) / (upper - lower) for value in values]
    assert 0.74 < statistics.mean(normalized) < 0.76
    assert 0.78 < statistics.median(normalized) < 0.81
    assert 0.86 < sum(v > 0.5 for v in normalized) / len(values) < 0.89
    assert 0.01 < sum(v < 0.25 for v in normalized) / len(values) < 0.022


def test_load_distribution_rejects_invalid_inputs_and_preserves_endpoints():
    assert biased_load_factor(0.2, 0.8, 0) == 0.2
    assert biased_load_factor(0.2, 0.8, 1) == pytest.approx(0.8)
    assert biased_load_factor(0.7, 0.7, 0.4) == 0.7
    for values in [
        (0, 1, 0.5),
        (0.8, 0.7, 0.5),
        (0.5, 1.1, 0.5),
        (0.5, 1, -0.1),
        (0.5, 1, 1.1),
        (float("nan"), 1, 0.5),
        (0.5, float("inf"), 0.5),
    ]:
        with pytest.raises(ValueError):
            biased_load_factor(*values)
