"""Historical game snapshots remain usable without current reference data."""

from unittest.mock import AsyncMock, patch

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
    monkeypatch, game
):
    contract = first_berlin_contract(game)
    original = game.transport_dispatch.planning.router.route
    game.transport_dispatch.planning.router.route = AsyncMock(
        side_effect=original
    )
    quote = project_quote(
        await game.quote_contract(contract["id"], "truck_01")
    )
    assert game.transport_dispatch.planning.router.route.await_count == 2
    game.transport_dispatch.planning.router.route.assert_any_await(
        contract["origin"]["lat"],
        contract["origin"]["lon"],
        contract["destination"]["lat"],
        contract["destination"]["lon"],
    )
    trip = project_transport(await game.dispatch(contract["id"], "truck_01"))
    with patch.object(
        game.world, "read", side_effect=WorldCatalogueError("offline")
    ):
        cash = game.player_state().cash
        set_game_clock(game, lambda: trip["arrives_at"] + 1)
        assert game.reconcile_arrival()
        assert game.player_state().cash == cash + trip["payout_eur"]
        assert not game.reconcile_arrival()
        assert (
            project_vehicle(game.get_vehicle("truck_01"))["hub"]
            == trip["destination_snapshot"]
        )
        for read_contracts in (game.list_contracts, game.refresh_contracts):
            with pytest.raises(WorldCatalogueError):
                read_contracts()
        assert game.dashboard().vehicles
    assert quote["origin"] == contract["origin"]


def test_api_projection_never_invents_missing_vehicle_locations(game):
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
        game.world, "read", side_effect=AssertionError("lookup")
    ):
        assert project_vehicle(vehicle)["hub"] is None
        known = game.state_repository.list_vehicles()[0]
        assert (
            project_vehicle(known)["hub"]["facility_uid"] == known.facility_uid
        )
