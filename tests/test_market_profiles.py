"""Strict Market v2 reference contracts and immutable value invariants."""

import math
import sqlite3
from dataclasses import FrozenInstanceError, replace

import pytest

from app.domain.errors import CatalogueError, WorldCatalogueError
from app.domain.market_profiles import (
    DISTANCE_BANDS,
    SEGMENT_SCALES,
    VEHICLE_SCALES,
    DistanceLoadProfile,
    TransportCapability,
    VehicleScaleProfile,
    require_unit_weight,
    vehicle_scale_for_segment,
)


def test_market_profiles_require_complete_immutable_values(world_catalogue):
    world = world_catalogue.read()
    profiles = {p.nhm_row_id: p for p in world.market_profiles}
    assert profiles
    for facility in world.facilities:
        for cargo in facility.nhm_profiles:
            profile = profiles[cargo.product.nhm_row_id]
            assert {p.distance_band for p in profile.distance_profiles} == set(
                DISTANCE_BANDS
            )
            assert {p.vehicle_scale for p in profile.scale_profiles} == set(
                VEHICLE_SCALES
            )
    first = next(iter(profiles.values()))
    with pytest.raises(FrozenInstanceError):
        first.transport_class = "special"
    for changes in (
        {"transport_class": "unknown"},
        {"value_eur_per_t": 0},
        {"freight_rate_factor_game": math.inf},
        {"distance_profiles": first.distance_profiles[:2]},
        {"distance_profiles": (first.distance_profiles[0],) * 3},
        {"scale_profiles": first.scale_profiles[:3]},
        {"scale_profiles": (first.scale_profiles[0],) * 4},
    ):
        with pytest.raises(ValueError):
            replace(first, **changes)


def test_market_profile_small_values_reject_invalid_weights():
    for invalid in (-1, 1.1, math.inf, math.nan, True):
        with pytest.raises(ValueError):
            require_unit_weight(invalid)
    for value in (0, 0.5, 1):
        require_unit_weight(value)
    for args in (
        ("invalid", 1, 0.2, 0.9),
        ("short", 1, 0, 1),
        ("long", 1, 0.9, 0.2),
    ):
        with pytest.raises(ValueError):
            replace(
                DistanceLoadProfile("short", 1, 0.2, 0.9),
                distance_band=args[0],
                selection_weight=args[1],
                load_factor_min=args[2],
                load_factor_max=args[3],
            )
    with pytest.raises(ValueError):
        TransportCapability("unknown", 1)
    with pytest.raises(ValueError):
        replace(VehicleScaleProfile("van", 1), vehicle_scale="unknown")
    for segment, scale in SEGMENT_SCALES.items():
        assert vehicle_scale_for_segment(segment) == scale
    with pytest.raises(ValueError):
        vehicle_scale_for_segment("unknown")


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE metadata SET value='4.0.0' WHERE key='schema_version'",
        "UPDATE metadata SET value='4.1.0' WHERE key='schema_version'",
        "DROP TABLE nhm_market_profiles",
        "DROP TABLE nhm_distance_load_profiles",
        "DROP TABLE nhm_vehicle_scale_profiles",
        "DELETE FROM nhm_market_profiles WHERE nhm_row_id=(SELECT nhm_row_id FROM facility_nhm_profiles LIMIT 1)",
        "DELETE FROM nhm_distance_load_profiles WHERE distance_band='short'",
        "DELETE FROM nhm_vehicle_scale_profiles WHERE vehicle_scale='van'",
        "UPDATE nhm_market_profiles SET transport_class='invalid'",
        "UPDATE nhm_market_profiles SET value_eur_per_t=0",
        "UPDATE nhm_market_profiles SET freight_rate_factor_game=0",
        "UPDATE nhm_market_profiles SET value_confidence=2",
        "UPDATE nhm_distance_load_profiles SET selection_weight=-1",
        "UPDATE nhm_distance_load_profiles SET load_factor_min=0",
        "UPDATE nhm_distance_load_profiles SET load_factor_min=1,load_factor_max=0.2",
        "UPDATE nhm_vehicle_scale_profiles SET suitability_game=2",
        "UPDATE nhm_market_profiles SET value_source_id=-1",
    ],
)
def test_world_market_profile_corruption_is_rejected(
    world_catalogue, mutation
):
    with sqlite3.connect(world_catalogue.path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.execute(mutation)
    with pytest.raises(WorldCatalogueError):
        world_catalogue.read()


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE catalog_metadata SET value='2.1.0' WHERE key='schema_version'",
        "DROP TABLE vehicle_transport_capabilities",
        "UPDATE vehicle_transport_capabilities SET transport_class='invalid' WHERE transport_class='general'",
        "UPDATE vehicle_transport_capabilities SET suitability_game=-1",
        "UPDATE vehicle_transport_capabilities SET suitability_game=2",
        "DELETE FROM vehicle_transport_capabilities",
        "UPDATE vehicle_models SET segment='unknown'",
    ],
)
def test_vehicle_market_profile_corruption_is_rejected(catalogue, mutation):
    with sqlite3.connect(catalogue.path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.execute(mutation)
    with pytest.raises(CatalogueError):
        catalogue.list_models()


def test_vehicle_model_capabilities_are_explicit_and_unique(catalogue):
    for model in catalogue.list_models():
        assert model.segment in SEGMENT_SCALES
        assert model.transport_capabilities
        for changes in (
            {"transport_capabilities": ()},
            {"transport_capabilities": model.transport_capabilities * 2},
            {"segment": "unknown"},
        ):
            with pytest.raises(ValueError):
                replace(model, **changes)
