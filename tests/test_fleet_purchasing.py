"""Vehicle purchasing, persisted economics and legacy compatibility."""

import sqlite3
from contextlib import closing
from unittest.mock import patch

import pytest

from app.api.v1.game_projection import (
    project_player,
    project_quote,
    project_transport,
    project_vehicle,
)
from app.domain.energy import EnergyProfile
from app.domain.game import OwnedVehicle, PlayerState
from app.services.gameplay.fleet import FleetService
from tests.support.game import first_berlin_contract
from tests.support.game_clock import set_game_clock


def test_purchase_reputation_snapshots_and_rollback(
    synthetic_game_context,
    synthetic_game,
    small_vehicle_catalogue,
):
    fleet = FleetService(
        synthetic_game.unit_of_work,
        small_vehicle_catalogue,
        synthetic_game_context.world,
    )
    with pytest.raises(ValueError, match="Reputation"):
        project_vehicle(fleet.purchase("daf_xg_plus_480"))
    player = project_player(synthetic_game.player_state())
    player.update(cash=500000, reputation=25)
    synthetic_game.state_repository.save_player(PlayerState(**player))
    vehicle = project_vehicle(fleet.purchase("daf_xg_plus_480"))
    rate = vehicle["operating_cost_eur_per_km"]
    assert vehicle["capacity_tons"] == 24.3
    assert synthetic_game.player_state().cash == 338000
    with (
        closing(sqlite3.connect(small_vehicle_catalogue.path)) as connection,
        connection,
    ):
        connection.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=9"
        )
    assert (
        project_vehicle(synthetic_game.get_vehicle(vehicle["id"]))[
            "operating_cost_eur_per_km"
        ]
        == rate
    )
    before = project_player(synthetic_game.player_state())
    vehicles = [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ]
    with patch.object(
        synthetic_game.state_repository,
        "save_vehicle",
        side_effect=RuntimeError("persistence failed"),
    ):
        with pytest.raises(RuntimeError):
            project_vehicle(fleet.purchase("iveco_sway_500"))
    assert project_player(synthetic_game.player_state()) == before
    assert [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ] == vehicles


async def test_vehicle_quotes_and_legacy_snapshots_remain_compatible(
    synthetic_game_context,
    synthetic_game,
    small_vehicle_catalogue,
):
    original = synthetic_game.state_repository.list_vehicles()[0]
    legacy = OwnedVehicle(
        original.id,
        original.name,
        original.mode,
        original.capacity_tons,
        original.facility_uid,
        original.status,
        location=original.location,
        energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
        energy_level=100,
        top_speed_kmh=90,
    )
    contract = first_berlin_contract(synthetic_game)
    synthetic_game.state_repository.save_vehicle(legacy)
    with pytest.raises(ValueError, match="Bestand"):
        await synthetic_game.quote_contract(contract["id"], "truck_01")
    synthetic_game.state_repository.save_vehicle(original)
    original._operating_cost_eur_per_km = 0.5
    synthetic_game.state_repository.save_vehicle(original)
    first = project_quote(
        await synthetic_game.quote_contract(contract["id"], "truck_01")
    )
    assert first["maintenance_eur_per_km"] == 0.078
    assert first["vehicle_id"] == "truck_01"
    vehicle = project_vehicle(
        FleetService(
            synthetic_game.unit_of_work,
            small_vehicle_catalogue,
            synthetic_game_context.world,
        ).purchase("iveco_sway_500")
    )
    quote = project_quote(
        await synthetic_game.quote_contract(contract["id"], vehicle["id"])
    )
    assert quote["operating_cost_eur"] == round(
        80 + quote["distance_km"] * quote["maintenance_eur_per_km"]
    )
    assert quote["payout_eur"] == first["payout_eur"]
    assert quote["operating_cost_eur"] == first["operating_cost_eur"]
    before = synthetic_game.player_state().cash
    trip = project_transport(
        await synthetic_game.dispatch(contract["id"], vehicle["id"])
    )
    assert trip["operating_cost_eur"] == quote["operating_cost_eur"]
    assert synthetic_game.player_state().cash == (
        before - quote["operating_cost_eur"]
    )
    synthetic_game.state_repository.save_player(
        PlayerState(cash=25000, reputation=0, completed=0)
    )
    for model_id in (None, "rigid_12t", "semi_24t"):
        legacy = OwnedVehicle(
            original.id,
            original.name,
            original.mode,
            original.capacity_tons,
            original.facility_uid,
            "idle",
            model_id=model_id,
            location=original.location,
            energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
            energy_level=100,
            top_speed_kmh=90,
        )
        synthetic_game.state_repository.save_vehicle(legacy)
        synthetic_game.ensure_initial_state()
        assert synthetic_game.player_state().cash == 25000
        assert (
            project_vehicle(synthetic_game.get_vehicle("truck_01"))["model_id"]
            == model_id
        )
    set_game_clock(synthetic_game, lambda: trip["arrives_at"] + 1)
    assert synthetic_game.get_vehicle(vehicle["id"]).status == "enroute"
    assert synthetic_game.reconcile_arrival()
    assert synthetic_game.player_state().cash == 25000 + trip["payout_eur"]
