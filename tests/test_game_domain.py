"""Behavior tests for typed player-owned game entities."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from app.api.v1.game_projection import project_player, project_vehicle
from app.api.v1.location_projection import project_location
from app.domain.contracts import ContractOffer, ContractOfferSnapshot
from app.domain.energy import EnergyProfile
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.world_scopes import WorldScope


def test_player_state_domain_rules():
    player = PlayerState(cash=1000, completed=2, reputation=3)
    player.debit(250)
    assert project_player(player) == {
        "cash": 750,
        "completed": 2,
        "reputation": 3,
    }

    player.complete_delivery(125)
    assert project_player(player) == {
        "cash": 875,
        "completed": 3,
        "reputation": 4,
    }

    with pytest.raises(ValueError, match="Debit"):
        player.debit(-1)
    with pytest.raises(ValueError, match="Nicht genug"):
        player.debit(1000)
    with pytest.raises(ValueError, match="Payout"):
        player.complete_delivery(-1)


def test_owned_vehicle_domain_rules(world_catalogue, catalogue):
    berlin = WorldScope(world_catalogue.read()).facility("berlin_westhafen")
    location = berlin.location_snapshot()
    vehicle = OwnedVehicle(
        id="truck_01",
        name="Test",
        mode="truck",
        model_id="legacy",
        operating_cost_eur_per_km=0.5,
        capacity_tons=24,
        facility_uid=berlin.facility_uid,
        location=location,
        status="idle",
        energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
        energy_level=100,
        top_speed_kmh=90,
    )

    assert vehicle.location == location
    vehicle.validate_dispatch("truck", location.city.city_uid, 20)

    with pytest.raises(ValueError, match="Abholstadt"):
        vehicle.validate_dispatch("truck", "elsewhere", 20)
    with pytest.raises(ValueError, match="kapazität"):
        vehicle.validate_dispatch("truck", location.city.city_uid, 25)
    with pytest.raises(ValueError, match="Fahrzeugtyp"):
        vehicle.validate_dispatch("ship", location.city.city_uid, 20)

    vehicle.start_trip()
    with pytest.raises(ValueError, match="verfügbar"):
        vehicle.validate_dispatch("truck", location.city.city_uid, 20)
    with pytest.raises(ValueError, match="verfügbar"):
        vehicle.start_trip()

    destination = next(
        facility
        for facility in world_catalogue.read().facilities
        if facility.facility_uid != berlin.facility_uid
    ).location_snapshot()
    vehicle.arrive(destination)
    assert vehicle.facility_uid == destination.facility_uid
    assert vehicle.location == destination
    assert vehicle.status == "idle"

    model = next(
        item for item in catalogue.list_models() if item.id == "man_tgx_520"
    )
    identity = vehicle.id
    vehicle.apply_model(model)
    assert vehicle.id == identity
    assert vehicle.model_id == model.id
    assert vehicle.capacity_tons == model.capacity_tons
    payload = project_vehicle(vehicle)
    assert payload["location_snapshot"] == project_location(destination)

    legacy = OwnedVehicle(
        id="legacy",
        name="Legacy",
        mode="truck",
        capacity_tons=12,
        facility_uid=berlin.facility_uid,
        status="idle",
        energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
        energy_level=100,
        top_speed_kmh=90,
    )
    assert project_vehicle(legacy)["model_id"] is None
    assert "location_snapshot" not in project_vehicle(legacy)


def test_contract_offer_domain_rules(game):
    offer = game.state_repository.list_offers()[0]

    assert offer.is_available(offer.created_at, offer.market_model)
    assert not offer.is_available(offer.expires_at, offer.market_model)
    assert not offer.is_available(offer.created_at, "other-model")

    snapshot = ContractOfferSnapshot(
        id=offer.id,
        market_model=offer.market_model,
        market_context=offer.market_context,
        cargo_system=offer.cargo_system,
        origin=offer.origin,
        destination=offer.destination,
        shipper_name=offer.shipper_name,
        consignee_name=offer.consignee_name,
        cargo=offer.cargo,
        origin_cargo_evidence=offer.origin_cargo_evidence,
        destination_cargo_evidence=offer.destination_cargo_evidence,
        cargo_basis=offer.cargo_basis,
        trade_match_type=offer.trade_match_type,
        tons=offer.tons,
        payload_band=offer.payload_band,
        rate_eur_per_km_ton=offer.rate_eur_per_km_ton,
        created_at=offer.created_at,
        expires_at=offer.expires_at,
        mode=offer.mode,
        relationship_simulated=offer.relationship_simulated,
    )
    assert ContractOffer.from_snapshot(snapshot) == offer

    for field in ("tons", "rate_eur_per_km_ton", "created_at", "expires_at"):
        with pytest.raises(ValueError):
            replace(offer, **{field: True})

    for changes in (
        {"id": ""},
        {"tons": 0},
        {"tons": float("nan")},
        {"rate_eur_per_km_ton": -1},
        {"created_at": float("inf")},
        {"expires_at": offer.created_at},
        {"destination": offer.origin},
        {"cargo": replace(offer.cargo, code="missing")},
    ):
        with pytest.raises(ValueError):
            replace(offer, **changes)
    assert not offer.is_available(offer.created_at - 1, offer.market_model)
    with pytest.raises(ValueError):
        offer.is_available(float("nan"), offer.market_model)


def test_domain_value_validators_reject_invalid_values():
    from app.domain.validation import (
        require_finite,
        require_identity,
        require_integer,
    )

    require_finite(0, "value")
    require_integer(0, "money")
    require_identity("known", "id")
    for value in (True, "1", float("inf"), float("nan"), -1):
        with pytest.raises(ValueError):
            require_finite(value, "value")
    for value in (True, 1.5, -1):
        with pytest.raises(ValueError):
            require_integer(value, "money")
    for value in (None, "", "  "):
        with pytest.raises(ValueError):
            require_identity(value, "id")


def test_entity_construction_and_mutation_are_guarded(
    world_catalogue, catalogue
):
    location = (
        WorldScope(world_catalogue.read())
        .facility("berlin_westhafen")
        .location_snapshot()
    )
    player = PlayerState(100, 2, 3)
    assert (player.cash, player.completed, player.reputation) == (100, 2, 3)
    player.replace_cash(90)
    assert player.cash == 90
    for field in ("cash", "completed", "reputation"):
        with pytest.raises(AttributeError):
            setattr(player, field, 5)
    invalid_values: list[Any] = [-1, True, 1.5]
    for value in invalid_values:
        with pytest.raises(ValueError):
            PlayerState(value, 0, 0)
        with pytest.raises(ValueError):
            player.replace_cash(value)
        with pytest.raises(ValueError):
            player.debit(value)
        with pytest.raises(ValueError):
            player.complete_delivery(value)
    with pytest.raises(ValueError):
        PlayerState(1, -1, 0)
    with pytest.raises(ValueError):
        PlayerState(1, 0, -1)
    base: dict[str, Any] = dict(
        id="v",
        name="Truck",
        mode="truck",
        capacity_tons=12,
        facility_uid=location.facility_uid,
        status="idle",
        location=location,
        model_id="legacy",
        operating_cost_eur_per_km=0.62,
    )
    vehicle = OwnedVehicle(
        **base,
        energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
        energy_level=100,
        top_speed_kmh=90,
    )
    for field, expected in base.items():
        assert getattr(vehicle, field) == expected
        with pytest.raises(AttributeError):
            setattr(vehicle, field, expected)
    for changes in (
        {"id": ""},
        {"name": ""},
        {"mode": ""},
        {"facility_uid": ""},
        {"capacity_tons": float("nan")},
        {"status": "unknown"},
        {"operating_cost_eur_per_km": -1},
        {"facility_uid": "other"},
        {"location": replace(location, facility_uid="other")},
    ):
        with pytest.raises(ValueError):
            OwnedVehicle(
                **{**base, **changes},
                energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
                energy_level=100,
                top_speed_kmh=90,
            )
    with pytest.raises(ValueError, match="travelling"):
        vehicle.arrive(location)
    with pytest.raises(ValueError):
        vehicle.validate_dispatch("truck", location.facility_uid, float("nan"))
    original = project_vehicle(vehicle)
    model = catalogue.list_models()[0]
    for changes in ({"capacity_tons": 0}, {"operating_cost_eur_per_km": -1}):
        with pytest.raises(ValueError):
            vehicle.apply_model(replace(model, **changes))
        assert project_vehicle(vehicle) == original
