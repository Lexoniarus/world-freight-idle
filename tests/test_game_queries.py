"""Read-only game queries and transport-safe API projections."""

from __future__ import annotations

from dataclasses import asdict, replace
from unittest.mock import patch

import pytest

from app.api.v1.game_projection import (
    project_contract,
    project_dashboard,
    project_state,
    project_transport,
    project_vehicle,
)
from app.domain.game import OwnedVehicle
from app.domain.world_scopes import WorldScope
from app.services.gameplay.game import GameService
from tests.support.catalogues import BERLIN_UID
from tests.support.game import first_berlin_contract
from tests.transport_fixtures import add_transport


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


def test_state_expands_contract_addresses(
    synthetic_game_context, synthetic_game: GameService
):
    state = project_state(synthetic_game.state())
    assert (
        state["hubs"][0]["address"]
        == WorldScope(synthetic_game_context.world.read())
        .facility(BERLIN_UID)
        .address.display_text()
    )
    assert "origin" in state["contracts"][0]
    assert "address" in state["contracts"][0]["origin"]


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


def test_contract_projection_retains_endpoint_snapshots(
    synthetic_game_context, synthetic_game
):
    offer = synthetic_game.state_repository.list_offers()[0]
    projected = project_contract(offer)
    assert projected["origin_hub_id"] == offer.origin.facility_uid
    assert projected["origin"]["address"] == offer.origin.address
    assert projected["destination"]["address"] == offer.destination.address

    with patch.object(
        synthetic_game_context.world,
        "read",
        side_effect=AssertionError("lookup"),
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


def test_list_get_and_expand_vehicles(
    synthetic_game_context, synthetic_game: GameService
):
    vehicles = [
        project_vehicle(value) for value in synthetic_game.list_vehicles()
    ]
    assert (
        vehicles[0]["hub"]["address"]
        == WorldScope(synthetic_game_context.world.read())
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
