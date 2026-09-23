"""Historical game snapshots remain usable without current reference data."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.game_projection import (
    project_contract,
    project_quote,
    project_state,
    project_transport,
    project_vehicle,
)
from app.domain.energy import EnergyProfile
from app.domain.errors import WorldCatalogueError
from app.domain.game import OwnedVehicle
from tests.test_game import first_berlin_contract


async def test_snapshot_routing_and_settlement_survive_catalogue_failure(
    monkeypatch, game
):
    contract = first_berlin_contract(game)
    original = game.router.route
    game.router.route = AsyncMock(side_effect=original)
    with patch.object(
        game.world, "read", side_effect=WorldCatalogueError("offline")
    ):
        quote = project_quote(await game.quote_contract(contract["id"]))
        game.router.route.assert_awaited_once_with(
            contract["origin"]["lat"],
            contract["origin"]["lon"],
            contract["destination"]["lat"],
            contract["destination"]["lon"],
        )
        trip = project_transport(
            await game.dispatch(contract["id"], "truck_01")
        )
        cash = game._get_player().cash
        monkeypatch.setattr(game, "now", lambda: trip["arrives_at"] + 1)
        assert game.reconcile_arrival()
        assert game._get_player().cash == cash + trip["payout_eur"]
        assert not game.reconcile_arrival()
        assert [project_vehicle(value) for value in game.list_vehicles()][0][
            "hub"
        ] == trip["destination_snapshot"]
        with pytest.raises(WorldCatalogueError):
            [
                project_contract(value)
                for value in game.refresh_market(force=True)
            ]
        game.state_repository.replace_offers(
            tuple(
                replace(item, created_at=0, expires_at=1)
                for item in game.state_repository.list_offers()
            )
        )
        assert [
            project_contract(value) for value in game.refresh_market()
        ] == []
        assert project_state(game.state())["vehicles"]
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
