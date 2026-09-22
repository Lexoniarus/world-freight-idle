"""Behavior tests for typed player-owned game entities."""

from __future__ import annotations

import pytest

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
