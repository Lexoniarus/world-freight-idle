"""Quote validation and atomic transport dispatch."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from app.api.v1.game_projection import (
    project_quote,
    project_transport,
    project_vehicle,
)
from app.domain.energy import EnergyProfile
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.journeys import unmetered_journey
from app.domain.pricing import PriceQuote
from app.domain.results import ContractQuote
from app.domain.transports import RouteSnapshot
from app.domain.world_scopes import WorldScope
from tests.support.game_service import FixturePlayerGameFacade
from tests.support.catalogues import BERLIN_UID
from tests.support.game import first_berlin_contract


@pytest.mark.asyncio
async def test_quote_contract_geocodes_routes_and_prices(
    synthetic_game_context,
    synthetic_game: FixturePlayerGameFacade,
):
    contract = first_berlin_contract(synthetic_game)
    quote = project_quote(
        await synthetic_game.quote_contract(contract["id"], "truck_01")
    )
    assert (
        quote["origin"]["address"]
        == WorldScope(synthetic_game_context.world.read())
        .facility(BERLIN_UID)
        .address.display_text()
    )
    assert quote["origin"]["coordinate_evidence"]
    assert quote["distance_km"] == 400.0
    assert quote["route_geojson"]["type"] == "LineString"
    assert quote["profit_eur"] == (
        quote["payout_eur"] - quote["operating_cost_eur"]
    )


@pytest.mark.asyncio
async def test_dispatch_builds_persisted_trip_and_debits_cost(
    synthetic_game_context,
    synthetic_game: FixturePlayerGameFacade,
):
    contract = first_berlin_contract(synthetic_game)
    before_cash = synthetic_game.player_state().cash
    trip = project_transport(
        await synthetic_game.dispatch(contract["id"], "truck_01")
    )
    after_cash = synthetic_game.player_state().cash
    assert (
        trip["origin"]["address"]
        == WorldScope(synthetic_game_context.world.read())
        .facility(BERLIN_UID)
        .address.display_text()
    )
    assert trip["route_geojson"]["type"] == "LineString"
    assert after_cash == before_cash - trip["operating_cost_eur"]
    assert [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ][0]["status"] == "enroute"


def test_validate_dispatch_checks_location_capacity_mode_and_status(
    synthetic_game_context,
    synthetic_game: FixturePlayerGameFacade,
):
    contract = first_berlin_contract(synthetic_game)
    vehicle = synthetic_game.state_repository.list_vehicles()[0]
    synthetic_game.transport_dispatch.validate_dispatch(
        vehicle,
        synthetic_game.transport_dispatch.find_contract(contract["id"]),
    )

    base: dict[str, Any] = dict(
        id=vehicle.id,
        name=vehicle.name,
        mode=vehicle.mode,
        capacity_tons=vehicle.capacity_tons,
        facility_uid=vehicle.facility_uid,
        status=vehicle.status,
        model_id=vehicle.model_id,
        location=vehicle.location,
    )
    from app.domain.world_scopes import WorldScope

    other_city = WorldScope(synthetic_game_context.world.read()).facility(
        "hamburg_cta"
    )
    for changes, message in (
        (
            {"facility_uid": other_city.facility_uid, "location": None},
            "Abholstadt",
        ),
        ({"capacity_tons": 0.1}, "kapazität"),
        ({"mode": "ship"}, "Fahrzeugtyp"),
        ({"status": "enroute"}, "verfügbar"),
    ):
        invalid = OwnedVehicle(
            **{**base, **changes},
            energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
            energy_level=100,
            top_speed_kmh=90,
        )
        with pytest.raises(ValueError, match=message):
            synthetic_game.transport_dispatch.validate_dispatch(
                invalid,
                synthetic_game.transport_dispatch.find_contract(
                    contract["id"]
                ),
            )


def test_build_trip_contains_tracking_timestamps(
    synthetic_game: FixturePlayerGameFacade,
):
    contract = first_berlin_contract(synthetic_game)
    quote = ContractQuote(
        synthetic_game.transport_dispatch.find_contract(contract["id"]),
        RouteSnapshot(((1, 2), (3, 4)), 10, 20, "p"),
        PriceQuote(100, 30, 70),
        "truck_01",
        0.62,
    )
    trip = synthetic_game.transport_dispatch.build_trip(
        synthetic_game.transport_dispatch.find_contract(contract["id"]),
        "truck_01",
        replace(quote, journey=unmetered_journey(10, 50)),
        1000.0,
    )
    with pytest.raises(ValueError, match="energy plan"):
        synthetic_game.transport_dispatch.build_trip(
            synthetic_game.transport_dispatch.find_contract(contract["id"]),
            "truck_01",
            quote,
            1000,
        )
    assert trip.departed_at == 1000.0
    assert trip.arrives_at == 1050.0
    assert trip.payout_eur - trip.operating_cost_eur == 70


@pytest.mark.asyncio
async def test_dispatch_rejects_insufficient_cash(
    synthetic_game: FixturePlayerGameFacade,
):
    contract = first_berlin_contract(synthetic_game)
    synthetic_game.state_repository.save_player(
        PlayerState(cash=0, completed=0, reputation=0)
    )
    with pytest.raises(ValueError, match="Nicht genug Geld"):
        project_transport(
            await synthetic_game.dispatch(contract["id"], "truck_01")
        )
