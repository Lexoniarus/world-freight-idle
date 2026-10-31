"""Counter-tests for deterministic support boundaries."""

import pytest

from tests.support.catalogues import (
    BERLIN_UID,
    build_synthetic_vehicle_catalogue,
    build_synthetic_world_catalogue,
)
from tests.support.manual_clock import ManualClock


def test_manual_clock_advances_without_accepting_invalid_intervals():
    source = [100.0]
    clock = ManualClock(lambda: source[0])

    assert clock() == 100
    assert clock.advance(25.5) == 125.5
    source[0] = 101
    assert clock() == 126.5
    for invalid in (0, -1, float("inf"), 86401):
        with pytest.raises(ValueError, match="out of range"):
            clock.advance(invalid)


def test_synthetic_catalogues_cover_gameplay_without_file_access():
    world = build_synthetic_world_catalogue().read()
    vehicles = build_synthetic_vehicle_catalogue().list_models()

    assert len(world.facilities) == 6
    assert world.facilities[0].facility_uid == BERLIN_UID
    distance_bands = {
        profile.distance_band
        for profile in world.market_profiles[0].distance_profiles
    }
    assert distance_bands == {
        "short",
        "medium",
        "long",
    }
    assert [model.id for model in vehicles] == [
        "iveco_sway_500",
        "renault_t_high_520",
        "man_tgx_520",
        "daf_xg_plus_480",
        "scania_r460_gas",
        "mercedes_eactros_600",
    ]
