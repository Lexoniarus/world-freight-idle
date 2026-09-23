from __future__ import annotations

import time
from dataclasses import asdict, replace
from typing import Any

import pytest

from app.api.v1.game_projection import (
    project_contract,
    project_dashboard,
    project_quote,
    project_state,
    project_transport,
    project_vehicle,
)
from app.domain.energy import EnergyProfile
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.journeys import unmetered_journey
from app.domain.pricing import PriceQuote
from app.domain.results import ContractQuote
from app.domain.transports import RouteSnapshot
from app.domain.world import FacilityQuery
from app.domain.world_scopes import WorldScope
from app.services.game import GameService
from tests.conftest import BERLIN_UID
from tests.transport_fixtures import add_transport


def first_berlin_contract(game: GameService) -> dict:
    return next(
        contract
        for contract in [
            project_contract(item)
            for item in game.state_repository.list_offers()
        ]
        if contract["origin_hub_id"] == BERLIN_UID
    )


def test_now_returns_wall_clock(game: GameService):
    before = time.time()
    observed = game.now()
    after = time.time()
    assert before <= observed <= after


def test_ensure_initial_state_is_idempotent(game: GameService):
    before = [
        project_vehicle(item) for item in game.state_repository.list_vehicles()
    ]
    game.ensure_initial_state()
    assert [
        project_vehicle(item) for item in game.state_repository.list_vehicles()
    ] == before
    assert game._get_player().cash == 175000


def test_refresh_market_reuses_fresh_market_and_can_force(game: GameService):
    first = [
        project_contract(value) for value in game.refresh_market(force=False)
    ]
    second = [
        project_contract(value) for value in game.refresh_market(force=False)
    ]
    forced = [
        project_contract(value) for value in game.refresh_market(force=True)
    ]
    assert second == first
    assert forced != first
    assert any(contract["origin_hub_id"] == BERLIN_UID for contract in forced)


@pytest.mark.asyncio
async def test_quote_contract_geocodes_routes_and_prices(game: GameService):
    contract = first_berlin_contract(game)
    quote = project_quote(await game.quote_contract(contract["id"]))
    assert (
        quote["origin"]["address"]
        == WorldScope(game.world.read())
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
    game: GameService,
):
    contract = first_berlin_contract(game)
    before_cash = game._get_player().cash
    trip = project_transport(await game.dispatch(contract["id"], "truck_01"))
    after_cash = game._get_player().cash
    assert (
        trip["origin"]["address"]
        == WorldScope(game.world.read())
        .facility(BERLIN_UID)
        .address.display_text()
    )
    assert trip["route_geojson"]["type"] == "LineString"
    assert after_cash == before_cash - trip["operating_cost_eur"]
    assert [
        project_vehicle(item) for item in game.state_repository.list_vehicles()
    ][0]["status"] == "enroute"


def test_reconcile_arrival_moves_vehicle_and_pays(game: GameService):
    contract = first_berlin_contract(game)
    quote = ContractQuote(
        game._find_contract(contract["id"]),
        RouteSnapshot(((13.3, 52.5), (9.9, 53.5)), 300, 100, "fake"),
        PriceQuote(1000, 200, 800),
        "truck_01",
        0.62,
    )
    trip = game._build_trip(
        game._find_contract(contract["id"]),
        "truck_01",
        replace(quote, journey=unmetered_journey(300, 1)),
        1.0,
    )
    game.state_repository.save_transport(trip)
    vehicle = game.state_repository.list_vehicles()[0]
    vehicle.start_trip()
    game.state_repository.save_vehicle(vehicle)
    before_cash = game._get_player().cash
    assert game.reconcile_arrival() is True
    assert game.reconcile_arrival() is False
    vehicle = [
        project_vehicle(item) for item in game.state_repository.list_vehicles()
    ][0]
    assert vehicle["hub_id"] == contract["destination_hub_id"]
    assert vehicle["status"] == "idle"
    assert game._get_player().cash == before_cash + 1000


def test_state_expands_contract_addresses(game: GameService):
    state = project_state(game.state())
    assert (
        state["hubs"][0]["address"]
        == WorldScope(game.world.read())
        .facility(BERLIN_UID)
        .address.display_text()
    )
    assert "origin" in state["contracts"][0]
    assert "address" in state["contracts"][0]["origin"]


def test_reset_restores_playable_state(game: GameService):
    game.state_repository.save_player(
        PlayerState(cash=1, completed=99, reputation=99)
    )
    state = project_state(game.reset())
    assert state["player"]["cash"] == 175000
    assert state["player"]["completed"] == 0
    assert len(state["vehicles"]) == 1


def test_find_contract_returns_match_and_raises(game: GameService):
    contract = first_berlin_contract(game)
    assert game._find_contract(contract["id"]).id == contract["id"]
    with pytest.raises(KeyError):
        game._find_contract("missing")
    future = replace(
        game._find_contract(contract["id"]), created_at=game.now() + 100
    )
    game.state_repository.replace_offers((future,))
    with pytest.raises(KeyError):
        game._find_contract(contract["id"])


def test_refresh_market_drops_legacy_offers_but_keeps_active_trips(
    game: GameService,
):
    current = game.refresh_market()
    legacy = replace(
        current[0], id="legacy-offer", market_model="previous-market"
    )
    trip = add_transport(game, arrives_at=game.now() + 1000)
    game.state_repository.replace_offers((legacy, *current))
    refreshed = [project_contract(value) for value in game.refresh_market()]
    assert all(item.get("market_model") == "nhm_v1" for item in refreshed)
    assert all(item["id"] != "legacy-offer" for item in refreshed)
    assert [
        asdict(item)
        for item in game.state_repository.list_transports()
        if item.status == "active"
    ] == [asdict(trip)]
    with pytest.raises(KeyError):
        game._find_contract("legacy-offer")


def test_find_vehicle_returns_match_and_raises(game: GameService):
    vehicles = game.state_repository.list_vehicles()
    assert game._find_vehicle(vehicles, "truck_01").name == (
        "IVECO S-Way 500 XC13"
    )
    with pytest.raises(ValueError):
        game._find_vehicle(vehicles, "missing")


def test_validate_dispatch_checks_location_capacity_mode_and_status(
    game: GameService,
):
    contract = first_berlin_contract(game)
    vehicle = game.state_repository.list_vehicles()[0]
    game._validate_dispatch(vehicle, game._find_contract(contract["id"]))

    base: dict[str, Any] = dict(
        id=vehicle.id,
        name=vehicle.name,
        mode=vehicle.mode,
        capacity_tons=vehicle.capacity_tons,
        facility_uid=vehicle.facility_uid,
        status=vehicle.status,
    )
    for changes, message in (
        ({"facility_uid": "hamburg_cta"}, "Abholadresse"),
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
            game._validate_dispatch(
                invalid, game._find_contract(contract["id"])
            )


def test_build_trip_contains_tracking_timestamps(game: GameService):
    contract = first_berlin_contract(game)
    quote = ContractQuote(
        game._find_contract(contract["id"]),
        RouteSnapshot(((1, 2), (3, 4)), 10, 20, "p"),
        PriceQuote(100, 30, 70),
        "truck_01",
        0.62,
    )
    trip = game._build_trip(
        game._find_contract(contract["id"]),
        "truck_01",
        replace(quote, journey=unmetered_journey(10, 50)),
        1000.0,
    )
    with pytest.raises(ValueError, match="energy plan"):
        game._build_trip(
            game._find_contract(contract["id"]), "truck_01", quote, 1000
        )
    assert trip.departed_at == 1000.0
    assert trip.arrives_at == 1050.0
    assert trip.payout_eur - trip.operating_cost_eur == 70


def test_contract_projection_retains_endpoint_snapshots(game):
    offer = game.state_repository.list_offers()[0]
    projected = project_contract(offer)
    assert projected["origin_hub_id"] == offer.origin.facility_uid
    assert projected["origin"]["address"] == offer.origin.address
    assert projected["destination"]["address"] == offer.destination.address
    from unittest.mock import patch

    with patch.object(
        game.world, "read", side_effect=AssertionError("lookup")
    ):
        assert project_contract(offer) == projected


def test_refresh_market_without_idle_vehicle_has_no_local_origins(
    game: GameService,
):
    vehicle = game.state_repository.list_vehicles()[0]
    vehicle.start_trip()
    game.state_repository.save_vehicle(vehicle)
    assert [
        project_contract(value) for value in game.refresh_market(force=True)
    ] == []


@pytest.mark.asyncio
async def test_dispatch_rejects_insufficient_cash(game: GameService):
    contract = first_berlin_contract(game)
    game.state_repository.save_player(
        PlayerState(cash=0, completed=0, reputation=0)
    )
    with pytest.raises(ValueError, match="Nicht genug Geld"):
        project_transport(await game.dispatch(contract["id"], "truck_01"))


def test_dashboard_returns_product_projection(game: GameService):
    payload = project_dashboard(game.dashboard())
    assert payload["player"]["cash"] == 175000
    assert payload["available_contracts"] == 0
    assert payload["idle_vehicles"] == 1
    assert payload["active_transports"] == 0
    assert "contracts" not in payload
    assert payload["featured_contracts"] == []
    assert payload["vehicles"]


def test_list_and_get_contracts_return_real_addresses(game: GameService):
    contracts = [project_contract(value) for value in game.list_contracts()]
    assert contracts
    assert {item["origin_hub_id"] for item in contracts} == {BERLIN_UID}

    viewport = [
        project_contract(value)
        for value in game.list_contracts(
            FacilityQuery.parse("-10,35,30,60"),
            game.market_scope.minimum_zoom,
        )
    ]
    assert len(viewport) > len(contracts)

    refreshed = [
        project_contract(value)
        for value in game.refresh_contracts(
            FacilityQuery.parse("-10,35,30,60"),
            game.market_scope.minimum_zoom,
        )
    ]
    assert refreshed != viewport
    contract = project_contract(game.get_contract(refreshed[0]["id"]))
    assert contract["origin"]["address"]
    assert contract["destination"]["address"]
    with pytest.raises(KeyError):
        project_contract(game.get_contract("missing"))


def test_list_get_and_expand_vehicles(game: GameService):
    vehicles = [project_vehicle(value) for value in game.list_vehicles()]
    assert (
        vehicles[0]["hub"]["address"]
        == WorldScope(game.world.read())
        .facility(BERLIN_UID)
        .address.display_text()
    )
    assert (
        project_vehicle(game.get_vehicle("truck_01"))["hub"]["city"]
        == "Berlin"
    )
    assert (
        project_vehicle(game.state_repository.list_vehicles()[0])["hub"]["id"]
        == BERLIN_UID
    )
    with pytest.raises(KeyError):
        project_vehicle(game.get_vehicle("missing"))


def test_list_and_get_transports(game: GameService):
    assert [project_transport(value) for value in game.list_transports()] == []
    with pytest.raises(KeyError):
        project_transport(game.get_transport("missing"))
    trip = add_transport(game, arrives_at=game.now() + 1000)
    assert [project_transport(value) for value in game.list_transports()] == [
        project_transport(trip)
    ]
    assert project_transport(game.get_transport(trip.id)) == project_transport(
        trip
    )
