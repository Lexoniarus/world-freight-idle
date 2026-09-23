"""Vehicle energy snapshots and explicit invalid-data counterexamples."""

import math
import sqlite3
from dataclasses import replace

import pytest

from app.domain.energy import EnergyProfile
from app.domain.errors import CatalogueError


def test_energy_profile_validates_measurements_and_consumption():
    profile = EnergyProfile("diesel", "l", 100, 20, 10, 0.1)
    assert profile.consumption_for(125) == 25
    assert profile.consumption_for(0) == 0
    profile.validate_level(0)
    profile.validate_level(100)
    for amount in (-1, 101, math.inf, math.nan, True):
        with pytest.raises(ValueError):
            profile.validate_level(amount)
    with pytest.raises(ValueError):
        profile.consumption_for(-1)
    for changes in (
        {"kind": "missing"},
        {"unit": "kg"},
        {"capacity": 0},
        {"consumption_per_100km": math.inf},
        {"stop_minutes": None},
        {"reserve_fraction": 1},
        {"reserve_fraction": 0},
    ):
        with pytest.raises(ValueError):
            replace(profile, **changes)


def test_catalogue_energy_values_match_all_fourteen_models(catalogue):
    models = catalogue.list_models()
    assert len(models) == 14
    for model in models:
        assert model.energy.capacity > 0
        assert model.top_speed_kmh > 0
        assert model.energy.reserve_fraction == 0.1
    iveco = next(m for m in models if m.id == "iveco_sway_500")
    assert iveco.energy == EnergyProfile("diesel", "l", 1010, 24.5, 10, 0.1)
    electric = next(m for m in models if m.id == "mercedes_eactros_600")
    assert electric.energy == EnergyProfile(
        "electric", "kWh", 600, 103, 35, 0.1
    )
    gas = next(m for m in models if m.id == "scania_r460_gas")
    assert gas.energy == EnergyProfile("gas", "kg", 400, 22.2, 25, 0.1)
    for changes in ({"top_speed_kmh": 0}, {"energy": None}):
        with pytest.raises(ValueError):
            replace(iveco, **changes)


@pytest.mark.parametrize(
    "column,value",
    [
        ("consumption_value", None),
        ("consumption_value", -1),
        ("consumption_value", math.inf),
        ("consumption_unit", "kg/100km"),
        ("fuel_tank_capacity_l", None),
        ("fuel_tank_capacity_l", 0),
        ("fuel_tank_capacity_kg", 100),
        ("top_speed_kmh", 0),
        ("top_speed_kmh", "fast"),
        ("powertrain", "unknown"),
    ],
)
def test_catalogue_rejects_incomplete_energy(catalogue, column, value):
    with sqlite3.connect(catalogue.path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.execute(
            f"UPDATE vehicle_models SET {column}=? "
            "WHERE vehicle_id='iveco_sway_500'",
            (value,),
        )
    with pytest.raises(CatalogueError):
        catalogue.list_models()


def test_catalogue_requires_non_diesel_stop_time(catalogue):
    with sqlite3.connect(catalogue.path) as db:
        db.execute(
            "UPDATE vehicle_balance SET energy_stop_minutes_game=NULL "
            "WHERE vehicle_id='mercedes_eactros_600'"
        )
    with pytest.raises(CatalogueError):
        catalogue.list_models()


def test_owned_energy_is_encapsulated_and_model_changes_preserve_fraction(
    game,
):
    vehicle = game.state_repository.list_vehicles()[0]
    from typing import Any

    from app.domain.game import OwnedVehicle

    invalid_energy: dict[str, Any] = {
        "energy": None,
        "energy_level": 0,
        "top_speed_kmh": 90,
    }
    with pytest.raises(ValueError, match="energy profile"):
        OwnedVehicle(
            "bad",
            "Invalid energy",
            "truck",
            24,
            vehicle.facility_uid,
            "idle",
            **invalid_energy,
        )
    original = vehicle.energy
    assert vehicle.energy_level == original.capacity
    assert vehicle.top_speed_kmh == 90
    vehicle.consume_energy(original.capacity / 2)
    assert vehicle.energy_level == original.capacity / 2
    for amount in (-1, math.inf, original.capacity):
        with pytest.raises(ValueError):
            vehicle.consume_energy(amount)
    model = next(
        m for m in game.catalogue.list_models() if m.energy.kind == "electric"
    )
    vehicle.apply_model(model)
    assert vehicle.energy == model.energy
    assert vehicle.energy_level == model.energy.capacity / 2
    game.state_repository.save_vehicle(vehicle)
    loaded = game.state_repository.list_vehicles()[0]
    assert loaded == vehicle
    vehicle.refill_energy()
    assert vehicle.energy_level == model.energy.capacity
    vehicle.start_trip()
    for operation in (
        lambda: vehicle.consume_energy(1),
        vehicle.refill_energy,
        lambda: vehicle.apply_model(model),
    ):
        with pytest.raises(ValueError):
            operation()
    with pytest.raises(ValueError):
        vehicle.arrive(vehicle.location, model.energy.capacity + 1)
    assert vehicle.status == "enroute"
    vehicle.arrive(vehicle.location, 60)
    assert vehicle.energy_level == 60
    for name in ("energy", "energy_level", "top_speed_kmh"):
        with pytest.raises(AttributeError):
            setattr(vehicle, name, None)
