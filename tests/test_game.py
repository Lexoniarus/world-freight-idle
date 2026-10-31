from __future__ import annotations

import time
from dataclasses import asdict, replace
from typing import Any
from unittest.mock import Mock, patch

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
from app.domain.world_scopes import WorldScope
from app.services.gameplay.game import GameService
from tests.support.catalogues import BERLIN_UID
from tests.support.game import first_berlin_contract
from tests.transport_fixtures import add_transport


def test_now_returns_wall_clock(synthetic_game: GameService):
    before = time.time()
    observed = synthetic_game.now()
    after = time.time()
    assert before <= observed <= after


def test_ensure_initial_state_is_idempotent(synthetic_game: GameService):
    before = [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ]
    synthetic_game.ensure_initial_state()
    assert [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ] == before
    assert synthetic_game.player_state().cash == 175000


def test_contract_reads_never_generate_inside_request(
    synthetic_game: GameService,
):
    first = [
        project_contract(value) for value in synthetic_game.list_contracts()
    ]
    second = [
        project_contract(value) for value in synthetic_game.list_contracts()
    ]
    forced = [
        project_contract(value) for value in synthetic_game.refresh_contracts()
    ]
    assert second == first
    assert forced == first
    assert any(contract["origin_hub_id"] == BERLIN_UID for contract in forced)


@pytest.mark.asyncio
async def test_quote_contract_geocodes_routes_and_prices(
    synthetic_game: GameService,
):
    contract = first_berlin_contract(synthetic_game)
    quote = project_quote(
        await synthetic_game.quote_contract(contract["id"], "truck_01")
    )
    assert (
        quote["origin"]["address"]
        == WorldScope(synthetic_game.world.read())
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
    synthetic_game: GameService,
):
    contract = first_berlin_contract(synthetic_game)
    before_cash = synthetic_game.player_state().cash
    trip = project_transport(
        await synthetic_game.dispatch(contract["id"], "truck_01")
    )
    after_cash = synthetic_game.player_state().cash
    assert (
        trip["origin"]["address"]
        == WorldScope(synthetic_game.world.read())
        .facility(BERLIN_UID)
        .address.display_text()
    )
    assert trip["route_geojson"]["type"] == "LineString"
    assert after_cash == before_cash - trip["operating_cost_eur"]
    assert [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ][0]["status"] == "enroute"


def test_reconcile_arrival_moves_vehicle_and_pays(synthetic_game: GameService):
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


def test_state_expands_contract_addresses(synthetic_game: GameService):
    state = project_state(synthetic_game.state())
    assert (
        state["hubs"][0]["address"]
        == WorldScope(synthetic_game.world.read())
        .facility(BERLIN_UID)
        .address.display_text()
    )
    assert "origin" in state["contracts"][0]
    assert "address" in state["contracts"][0]["origin"]


def test_reset_restores_playable_state(synthetic_game: GameService):
    demand = Mock()
    synthetic_game.initialization.market_demand = demand
    synthetic_game.state_repository.save_player(
        PlayerState(cash=1, completed=99, reputation=99)
    )
    state = project_state(synthetic_game.reset())
    assert state["player"]["cash"] == 175000
    assert state["player"]["completed"] == 0
    assert len(state["vehicles"]) == 1
    demand.invalidate.assert_called_once_with()


def test_find_contract_returns_match_and_raises(synthetic_game: GameService):
    contract = first_berlin_contract(synthetic_game)
    assert (
        synthetic_game.transport_dispatch.find_contract(contract["id"]).id
        == contract["id"]
    )
    with pytest.raises(KeyError):
        synthetic_game.transport_dispatch.find_contract("missing")
    future = replace(
        synthetic_game.transport_dispatch.find_contract(contract["id"]),
        created_at=synthetic_game.now() + 100,
    )
    synthetic_game.state_repository.replace_offers((future,))
    with pytest.raises(KeyError):
        synthetic_game.transport_dispatch.find_contract(contract["id"])


def test_contract_reads_drop_legacy_offers_but_keep_active_trips(
    synthetic_game: GameService,
):
    current = synthetic_game.list_contracts()
    legacy = replace(
        current[0], id="legacy-offer", market_model="previous-market"
    )
    trip = add_transport(
        synthetic_game, arrives_at=synthetic_game.now() + 1000
    )
    synthetic_game.state_repository.replace_offers((legacy, *current))
    refreshed = [
        project_contract(value) for value in synthetic_game.list_contracts()
    ]
    assert all(item.get("market_model") == "nhm_v2" for item in refreshed)
    assert all(item["id"] != "legacy-offer" for item in refreshed)
    assert [
        asdict(item)
        for item in synthetic_game.state_repository.list_transports()
        if item.status == "active"
    ] == [asdict(trip)]
    with pytest.raises(KeyError):
        synthetic_game.transport_dispatch.find_contract("legacy-offer")


def test_find_vehicle_returns_match_and_raises(synthetic_game: GameService):
    vehicles = synthetic_game.state_repository.list_vehicles()
    assert synthetic_game.transport_dispatch.find_vehicle(
        vehicles, "truck_01"
    ).name == ("IVECO S-Way 500 XC13")
    with pytest.raises(ValueError):
        synthetic_game.transport_dispatch.find_vehicle(vehicles, "missing")


def test_validate_dispatch_checks_location_capacity_mode_and_status(
    synthetic_game: GameService,
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

    other_city = WorldScope(synthetic_game.world.read()).facility(
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


def test_vehicle_location_resolution_is_explicit_and_eligibility_is_pure(
    synthetic_game: GameService,
):
    """Eligibility must not hide restoration of persisted vehicle state."""
    contract = synthetic_game.transport_dispatch.find_contract(
        first_berlin_contract(synthetic_game)["id"]
    )
    stored = synthetic_game.state_repository.list_vehicles()[0]
    vehicle = OwnedVehicle(
        id=stored.id,
        name=stored.name,
        mode=stored.mode,
        capacity_tons=stored.capacity_tons,
        facility_uid=stored.facility_uid,
        status=stored.status,
        model_id=stored.model_id,
        location=None,
        energy=stored.energy,
        energy_level=stored.energy_level,
        top_speed_kmh=stored.top_speed_kmh,
    )

    with pytest.raises(ValueError, match="Abholstadt"):
        synthetic_game.transport_dispatch.eligibility.require_eligible(
            vehicle, contract
        )
    assert vehicle.location is None

    synthetic_game.transport_dispatch.vehicle_locations.resolve(vehicle)
    synthetic_game.transport_dispatch.eligibility.require_eligible(
        vehicle, contract
    )
    assert vehicle.location is not None


def test_build_trip_contains_tracking_timestamps(synthetic_game: GameService):
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


def test_contract_projection_retains_endpoint_snapshots(synthetic_game):
    offer = synthetic_game.state_repository.list_offers()[0]
    projected = project_contract(offer)
    assert projected["origin_hub_id"] == offer.origin.facility_uid
    assert projected["origin"]["address"] == offer.origin.address
    assert projected["destination"]["address"] == offer.destination.address
    from unittest.mock import patch

    with patch.object(
        synthetic_game.world, "read", side_effect=AssertionError("lookup")
    ):
        assert project_contract(offer) == projected


def test_contract_refresh_without_idle_vehicle_has_no_local_origins(
    synthetic_game: GameService,
):
    vehicle = synthetic_game.state_repository.list_vehicles()[0]
    vehicle.start_trip()
    synthetic_game.state_repository.save_vehicle(vehicle)
    assert [
        project_contract(value) for value in synthetic_game.refresh_contracts()
    ] == []


@pytest.mark.asyncio
async def test_dispatch_rejects_insufficient_cash(synthetic_game: GameService):
    contract = first_berlin_contract(synthetic_game)
    synthetic_game.state_repository.save_player(
        PlayerState(cash=0, completed=0, reputation=0)
    )
    with pytest.raises(ValueError, match="Nicht genug Geld"):
        project_transport(
            await synthetic_game.dispatch(contract["id"], "truck_01")
        )


def test_dashboard_returns_product_projection(synthetic_game: GameService):
    payload = project_dashboard(synthetic_game.dashboard())
    assert payload["player"]["cash"] == 175000
    assert payload["available_contracts"] == 0
    assert payload["idle_vehicles"] == 1
    assert payload["active_transports"] == 0
    assert "contracts" not in payload
    assert payload["featured_contracts"] == []
    assert payload["vehicles"]


def test_list_and_get_contracts_return_real_addresses(
    synthetic_game: GameService,
):
    contracts = [
        project_contract(value) for value in synthetic_game.list_contracts()
    ]
    assert contracts
    location = synthetic_game.get_vehicle("truck_01").location
    assert location is not None
    assert {item["origin"]["city_uid"] for item in contracts} == {
        location.city.city_uid
    }
    assert len({item["origin_hub_id"] for item in contracts}) > 1
    assert [
        project_contract(value) for value in synthetic_game.list_contracts()
    ] == contracts
    refreshed = [
        project_contract(value) for value in synthetic_game.refresh_contracts()
    ]
    assert refreshed == contracts
    contract = project_contract(
        synthetic_game.get_contract(refreshed[0]["id"])
    )
    assert contract["origin"]["address"]
    assert contract["destination"]["address"]
    with pytest.raises(KeyError):
        project_contract(synthetic_game.get_contract("missing"))


def test_market_presentation_filters_coverage_for_requested_vehicle(
    synthetic_game: GameService,
):
    offers = synthetic_game.list_contracts()
    presentation = synthetic_game.market_presentation(offers, "truck_01")

    assert presentation.contracts == synthetic_game.contract_choices(
        offers,
        "truck_01",
    )
    assert presentation.vehicle_coverage == tuple(
        item
        for item in synthetic_game.vehicle_coverage()
        if item.vehicle_id == "truck_01"
    )


@pytest.mark.asyncio
async def test_settlement_rejects_transport_without_owned_vehicle(
    synthetic_game: GameService,
):
    contract = first_berlin_contract(synthetic_game)
    trip = await synthetic_game.dispatch(contract["id"], "truck_01")

    with patch.object(
        synthetic_game.state_repository, "list_vehicles", return_value=()
    ):
        with pytest.raises(ValueError, match="Fahrzeug existiert nicht"):
            synthetic_game.settlement.complete_trip(trip, trip.arrives_at + 1)


def test_list_get_and_expand_vehicles(synthetic_game: GameService):
    vehicles = [
        project_vehicle(value) for value in synthetic_game.list_vehicles()
    ]
    assert (
        vehicles[0]["hub"]["address"]
        == WorldScope(synthetic_game.world.read())
        .facility(BERLIN_UID)
        .address.display_text()
    )
    assert (
        project_vehicle(synthetic_game.get_vehicle("truck_01"))["hub"]["city"]
        == "Berlin"
    )
    assert (
        project_vehicle(synthetic_game.state_repository.list_vehicles()[0])[
            "hub"
        ]["id"]
        == BERLIN_UID
    )
    with pytest.raises(KeyError):
        project_vehicle(synthetic_game.get_vehicle("missing"))


def test_list_and_get_transports(synthetic_game: GameService):
    assert [
        project_transport(value) for value in synthetic_game.list_transports()
    ] == []
    with pytest.raises(KeyError):
        project_transport(synthetic_game.get_transport("missing"))
    trip = add_transport(
        synthetic_game, arrives_at=synthetic_game.now() + 1000
    )
    assert [
        project_transport(value) for value in synthetic_game.list_transports()
    ] == [project_transport(trip)]
    assert project_transport(
        synthetic_game.get_transport(trip.id)
    ) == project_transport(trip)
