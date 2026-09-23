"""Behavior tests for typed player-owned game entities."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain.contracts import ContractOffer, ContractOfferSnapshot
from app.domain.game import OwnedVehicle, PlayerState


def test_player_state_domain_rules():
    player = PlayerState.from_dict(
        {"cash": 1000, "completed": 2, "reputation": 3}
    )
    player.debit(250)
    assert player.to_dict() == {
        "cash": 750,
        "completed": 2,
        "reputation": 3,
    }

    player.complete_delivery(125)
    assert player.to_dict() == {
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
    berlin = world_catalogue.read().get_facility("berlin_westhafen")
    location = berlin.location_snapshot()
    vehicle = OwnedVehicle.from_dict(
        {
            "id": "truck_01",
            "name": "Test",
            "mode": "truck",
            "model_id": "legacy",
            "operating_cost_eur_per_km": 0.5,
            "capacity_tons": 24,
            "hub_id": berlin.facility_uid,
            "facility_uid": berlin.facility_uid,
            "location_snapshot": location.to_dict(),
            "status": "idle",
        }
    )

    assert vehicle.location == location
    vehicle.validate_dispatch("truck", berlin.facility_uid, 20)

    with pytest.raises(ValueError, match="Abholadresse"):
        vehicle.validate_dispatch("truck", "elsewhere", 20)
    with pytest.raises(ValueError, match="kapazität"):
        vehicle.validate_dispatch("truck", berlin.facility_uid, 25)
    with pytest.raises(ValueError, match="Fahrzeugtyp"):
        vehicle.validate_dispatch("ship", berlin.facility_uid, 20)

    vehicle.start_trip()
    with pytest.raises(ValueError, match="verfügbar"):
        vehicle.validate_dispatch("truck", berlin.facility_uid, 20)
    with pytest.raises(ValueError, match="verfügbar"):
        vehicle.start_trip()

    destination = next(
        facility
        for facility in world_catalogue.read().facilities
        if facility.facility_uid != berlin.facility_uid
    ).location_snapshot()
    vehicle.arrive(destination)
    assert vehicle.hub_id == destination.facility_uid
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
    payload = vehicle.to_dict()
    assert payload["location_snapshot"] == destination.to_dict()

    legacy = OwnedVehicle.from_dict(
        {
            "id": "legacy",
            "name": "Legacy",
            "mode": "truck",
            "capacity_tons": 12,
            "hub_id": berlin.facility_uid,
            "status": "idle",
        }
    )
    assert legacy.to_dict()["model_id"] is None
    assert "location_snapshot" not in legacy.to_dict()


def test_contract_offer_domain_rules(game):
    payload = game.store.get_json("contracts")[0]
    offer = ContractOffer.from_dict(payload)

    assert offer.to_dict() == payload
    assert offer.is_available(offer.created_at, offer.market_model)
    assert not offer.is_available(offer.expires_at, offer.market_model)
    assert not offer.is_available(offer.created_at, "other-model")

    snapshot = ContractOfferSnapshot(
        id=offer.id,
        market_model=offer.market_model,
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

    broken = {**payload, "cargo_code": "not-in-evidence"}
    with pytest.raises(ValueError, match="Cargo code"):
        ContractOffer.from_dict(broken)

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
