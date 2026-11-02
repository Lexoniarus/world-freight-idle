"""Arrival settlement and owned-vehicle integrity."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.api.v1.game_projection import (
    project_vehicle,
)
from app.domain.journeys import unmetered_journey
from app.domain.pricing import PriceQuote
from app.domain.results import ContractQuote
from app.domain.transports import RouteSnapshot
from tests.support.game_service import FixturePlayerGameFacade
from tests.support.game import first_berlin_contract


def test_reconcile_arrival_moves_vehicle_and_pays(
    synthetic_game: FixturePlayerGameFacade,
):
    contract = first_berlin_contract(synthetic_game)
    quote = ContractQuote(
        synthetic_game.transport_dispatch.find_contract(contract["id"]),
        RouteSnapshot(((13.3, 52.5), (9.9, 53.5)), 300, 100, "fake"),
        PriceQuote(1000, 200, 800),
        "truck_01",
        0.62,
    )
    trip = synthetic_game.transport_dispatch.build_trip(
        synthetic_game.transport_dispatch.find_contract(contract["id"]),
        "truck_01",
        replace(quote, journey=unmetered_journey(300, 1)),
        1.0,
    )
    synthetic_game.state_repository.save_transport(trip)
    vehicle = synthetic_game.state_repository.list_vehicles()[0]
    vehicle.start_trip()
    synthetic_game.state_repository.save_vehicle(vehicle)
    before_cash = synthetic_game.player_state().cash
    assert synthetic_game.reconcile_arrival() is True
    assert synthetic_game.reconcile_arrival() is False
    vehicle = [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ][0]
    assert vehicle["hub_id"] == contract["destination_hub_id"]
    assert vehicle["status"] == "idle"
    assert synthetic_game.player_state().cash == before_cash + 1000


@pytest.mark.asyncio
async def test_settlement_rejects_transport_without_owned_vehicle(
    synthetic_game: FixturePlayerGameFacade,
):
    contract = first_berlin_contract(synthetic_game)
    trip = await synthetic_game.dispatch(contract["id"], "truck_01")

    with patch.object(
        synthetic_game.state_repository, "list_vehicles", return_value=()
    ):
        with pytest.raises(ValueError, match="Fahrzeug existiert nicht"):
            synthetic_game.settlement.complete_trip(trip, trip.arrives_at + 1)
