"""City market selection, coverage and immutable materialization behavior."""

import math

import pytest

from app.domain.geography import Coordinates
from app.domain.market_calculations import (
    distance_band,
    great_circle_km,
    shipment_tons,
)


def test_distance_and_tonnage_are_deterministic_and_bounded():
    assert [distance_band(d) for d in (0, 150, 150.0001, 600, 600.0001)] == [
        "short",
        "short",
        "medium",
        "medium",
        "long",
    ]
    assert great_circle_km(Coordinates(0, 0), Coordinates(0, 0)) == 0
    assert great_circle_km(
        Coordinates(0, 0), Coordinates(0, 180)
    ) == pytest.approx(20015.1144, rel=1e-6)
    assert great_circle_km(
        Coordinates(0, 179), Coordinates(0, -179)
    ) == pytest.approx(222.39, rel=1e-4)
    for bad in (-1, math.nan, math.inf):
        with pytest.raises(ValueError):
            distance_band(bad)
    assert shipment_tons(0.01, 0.5) == 0.01
    assert shipment_tons(1.157, 1) == 1.15
    assert shipment_tons(24.2, 0.5) == 12.1
    for capacity, load in ((0, 1), (1, 0), (1, 1.1), (math.inf, 0.5)):
        with pytest.raises(ValueError):
            shipment_tons(capacity, load)
