"""Counter-tests for deterministic support boundaries."""

from pathlib import Path

import pytest

from tests.support.application_settings import (
    build_synthetic_application_settings,
)
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


def test_synthetic_application_settings_use_compact_sql_catalogues(tmp_path):
    settings = build_synthetic_application_settings(tmp_path)

    assert settings.world_catalogue_path is not None
    assert settings.vehicle_catalogue_path is not None
    assert settings.world_catalogue_path.parent == tmp_path
    assert settings.vehicle_catalogue_path.parent == tmp_path
    assert settings.world_catalogue_path.stat().st_size < 200_000
    assert settings.vehicle_catalogue_path.stat().st_size < 100_000


def test_reference_catalogue_fixtures_are_acceptance_only():
    tests_root = Path(__file__).parent
    consumers = {
        fixture: {
            path.name
            for path in tests_root.glob("test_*.py")
            if path != Path(__file__)
            if fixture in path.read_text(encoding="utf-8")
        }
        for fixture in (
            "reference_vehicle_catalogue",
            "reference_world_catalogue",
        )
    }

    assert consumers == {
        "reference_vehicle_catalogue": {"test_vehicle_catalogue.py"},
        "reference_world_catalogue": {"test_world_catalogue.py"},
    }


def test_reference_catalogue_paths_stay_out_of_behavior_tests():
    tests_root = Path(__file__).parent
    consumers = {
        path.name
        for path in tests_root.glob("test_*.py")
        if path != Path(__file__)
        if "REFERENCE_WORLD_PATH" in path.read_text(encoding="utf-8")
        or "REFERENCE_VEHICLE_PATH" in path.read_text(encoding="utf-8")
    }

    assert consumers == set()
