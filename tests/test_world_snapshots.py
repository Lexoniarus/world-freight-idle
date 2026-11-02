"""Historical game snapshots remain usable without current reference data."""

from unittest.mock import patch

import pytest

from app.api.v1.game_projection import (
    project_quote,
    project_transport,
    project_vehicle,
)
from app.domain.energy import EnergyProfile
from app.domain.errors import WorldCatalogueError
from app.domain.game import OwnedVehicle
from tests.support.game import first_berlin_contract
from tests.support.game_clock import set_game_clock


async def test_snapshot_routing_and_settlement_survive_catalogue_failure(
    synthetic_game_context, monkeypatch, synthetic_game
):
    contract = first_berlin_contract(synthetic_game)
    readiness = synthetic_game.market_services.routes.readiness
    with patch.object(readiness, "load", wraps=readiness.load) as loaded:
        quote = project_quote(
            await synthetic_game.quote_contract(contract["id"], "truck_01")
        )
    assert loaded.call_count == 2
    trip = project_transport(
        await synthetic_game.dispatch(contract["id"], "truck_01")
    )
    with patch.object(
        synthetic_game_context.world,
        "read",
        side_effect=WorldCatalogueError("offline"),
    ):
        cash = synthetic_game.player_state().cash
        set_game_clock(synthetic_game, lambda: trip["arrives_at"] + 1)
        assert synthetic_game.reconcile_arrival()
        assert synthetic_game.player_state().cash == cash + trip["payout_eur"]
        assert not synthetic_game.reconcile_arrival()
        assert (
            project_vehicle(synthetic_game.get_vehicle("truck_01"))["hub"]
            == trip["destination_snapshot"]
        )
        for read_contracts in (
            synthetic_game.list_contracts,
            synthetic_game.refresh_contracts,
        ):
            with pytest.raises(WorldCatalogueError):
                read_contracts()
        assert synthetic_game.dashboard().vehicles
    assert quote["origin"] == contract["origin"]


def test_api_projection_never_invents_missing_vehicle_locations(
    synthetic_game_context,
    synthetic_game,
):
    vehicle = OwnedVehicle(
        "unknown",
        "Unknown",
        "truck",
        12,
        "unknown",
        "idle",
        energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
        energy_level=100,
        top_speed_kmh=90,
    )
    with patch.object(
        synthetic_game_context.world,
        "read",
        side_effect=AssertionError("lookup"),
    ):
        assert project_vehicle(vehicle)["hub"] is None
        known = synthetic_game.state_repository.list_vehicles()[0]
        assert (
            project_vehicle(known)["hub"]["facility_uid"] == known.facility_uid
        )
