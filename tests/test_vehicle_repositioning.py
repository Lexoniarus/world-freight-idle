"""Owned-vehicle repositioning invariants."""

import pytest


def test_reposition_rejects_busy_other_city_and_missing_location(
    synthetic_game,
):
    vehicle = synthetic_game.get_vehicle("truck_01")
    offer = next(
        item
        for item in synthetic_game.list_contracts()
        if item.destination.city.city_uid != vehicle.location.city.city_uid
    )
    with pytest.raises(ValueError, match="same city"):
        vehicle.reposition_within_city(offer.destination)
    vehicle.start_trip()
    with pytest.raises(ValueError, match="idle"):
        vehicle.reposition_within_city(offer.origin)
    vehicle.arrive(offer.origin)
    vehicle._location = None
    with pytest.raises(ValueError, match="same city"):
        vehicle.reposition_within_city(offer.origin)
