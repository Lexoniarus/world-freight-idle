import random
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.domain.errors import WorldCatalogueError
from app.services.market import MarketGenerator
from app.simulation import PayloadBand, build_payload_bands


def test_market_generate_guarantees_origin_and_real_addresses_are_external(
    world_catalogue,
    catalogue,
):
    market = MarketGenerator(world_catalogue, random.Random(3), catalogue)
    contracts = market.generate(1000, ["berlin_westhafen", "missing"], 4)
    berlin = world_catalogue.read().get_facility("berlin_westhafen")
    assert len(contracts) == 43 * len(
        build_payload_bands([m.capacity_tons for m in catalogue.list_models()])
    )
    assert contracts[0]["origin_facility_uid"] == berlin.facility_uid
    for contract in contracts:
        assert contract["origin_hub_id"] != contract["destination_hub_id"]
        assert contract["relationship_simulated"] is True
        assert contract["origin"]["coordinate_evidence"]
        assert contract["destination"]["coordinate_evidence"]


def test_build_contract_has_expiry_and_valid_cargo(world_catalogue, catalogue):
    snapshot = world_catalogue.read()
    origin = snapshot.get_facility("berlin_westhafen")
    destination = replace(origin, facility_uid="another-facility")
    market = MarketGenerator(world_catalogue, random.Random(3), catalogue)
    contract = market._build_contract(
        origin, (origin, destination), 1000, PayloadBand("heavy", 24)
    )
    assert contract["expires_at"] == 22600
    assert contract["cargo"] in {c.name for c in origin.outbound_cargo()}
    assert 8 <= contract["tons"] <= 24
    assert contract["rate_eur_per_km_ton"] == 0.18
    assert contract["destination_facility_uid"] == "another-facility"
    with pytest.raises(IndexError):
        market._build_contract(
            origin, (origin,), 1000, PayloadBand("heavy", 24)
        )
    small_world = Mock(
        read=Mock(
            return_value=replace(snapshot, facilities=(origin, destination))
        )
    )
    generated = MarketGenerator(
        small_world, random.Random(3), catalogue
    ).generate(1000, [], 10)
    assert len(generated) == 10
    assert {item["origin_facility_uid"] for item in generated} == {
        origin.facility_uid,
        destination.facility_uid,
    }


def test_market_generate_rejects_world_without_onward_work(
    world_catalogue, catalogue
):
    snapshot = world_catalogue.read()
    world = Mock(read=Mock(return_value=replace(snapshot, facilities=())))
    with pytest.raises(WorldCatalogueError):
        MarketGenerator(world, random.Random(1), catalogue).generate(1, [])


def test_every_routable_facility_has_work_and_mock_goods_are_explicit(
    world_catalogue,
    catalogue,
):
    market = MarketGenerator(world_catalogue, random.Random(3), catalogue)
    facilities = world_catalogue.read().facilities
    contracts = market.generate(1000, ["berlin_westhafen", "berlin_westhafen"])
    assert {c["origin_facility_uid"] for c in contracts} == {
        f.facility_uid for f in facilities if f.is_routable()
    }
    simulated = [c for c in contracts if c["cargo_basis"] == "simulated"]
    assert len(simulated) == 19 * len(
        build_payload_bands([m.capacity_tons for m in catalogue.list_models()])
    )
    assert all(
        c["cargo_evidence"] is None
        and c["cargo"] == "Standardfracht (Simulation)"
        for c in simulated
    )
    assert all(
        c["cargo_evidence"]
        for c in contracts
        if c["cargo_basis"] == "documented"
    )
    remaining = contracts[1:]
    refilled = market.generate(1001, [], existing_contracts=remaining)
    assert refilled[: len(remaining)] == remaining
    assert len(refilled) == len(contracts)
    assert (
        refilled[-1]["origin_facility_uid"]
        == contracts[0]["origin_facility_uid"]
    )
    assert market.generate(1002, [], existing_contracts=refilled) == refilled


def test_payload_bands_cover_catalogue_and_reject_invalid_capacities():
    assert build_payload_bands([1.15, 1.1, 2, 5.1, 5.3, 22, 24.3]) == (
        PayloadBand("light", 1.1),
        PayloadBand("medium", 5.1),
        PayloadBand("heavy", 22),
    )
    assert build_payload_bands([3.5, 12, 12.01]) == (
        PayloadBand("light", 3.5),
        PayloadBand("medium", 12),
        PayloadBand("heavy", 12.01),
    )
    assert build_payload_bands([0.01]) == (PayloadBand("light", 0.01),)
    for capacities in ([], [0], [-1], [float("nan")], [float("inf")]):
        with pytest.raises(ValueError, match="capacities"):
            build_payload_bands(capacities)


def test_every_payload_can_work_at_every_facility_and_refill_keeps_ids(
    world_catalogue,
):
    capacities = [1.15, 1.1, 1.2, 2, 5.1, 5.3, 22, 24.3]
    vehicles = Mock(
        list_models=Mock(
            return_value=[
                SimpleNamespace(capacity_tons=value) for value in capacities
            ]
        )
    )
    market = MarketGenerator(world_catalogue, random.Random(5), vehicles)
    contracts = market.generate(1000, [])
    assert len(contracts) == 129
    for facility in world_catalogue.read().facilities:
        if facility.is_routable():
            local = [
                c
                for c in contracts
                if c["origin_hub_id"] == facility.facility_uid
            ]
            assert {c["payload_band"] for c in local} == {
                "light",
                "medium",
                "heavy",
            }
            for capacity in capacities:
                assert any(0 < c["tons"] <= capacity for c in local)
            assert not all(c["tons"] <= 1.1 for c in local)
    legacy = {**contracts[0], "id": "unchanged-legacy", "tons": 24}
    legacy.pop("payload_band")
    retained = [legacy, *contracts[1:]]
    refilled = market.generate(1001, [], existing_contracts=retained)
    assert refilled[: len(retained)] == retained
    assert len(refilled) == 130
    vehicles.list_models.return_value = [SimpleNamespace(capacity_tons=0.01)]
    tiny = market.generate(1002, [], existing_contracts=refilled)
    assert len([c for c in tiny if c["tons"] == 0.01]) == 43
    vehicles.list_models.return_value = [SimpleNamespace(capacity_tons=24)]
    legacy_fleet = market.generate(1003, [], owned_capacities=[12])
    assert len(legacy_fleet) == 86
    assert {c["payload_band"] for c in legacy_fleet} == {"medium", "heavy"}


def test_vehicle_catalogue_outage_preserves_existing_market(game, monkeypatch):
    from app.domain.errors import CatalogueError

    original = game.refresh_market()
    monkeypatch.setattr(
        game.market.vehicles,
        "list_models",
        Mock(side_effect=CatalogueError("offline")),
    )
    assert game.refresh_market() == original
    with pytest.raises(CatalogueError, match="offline"):
        game.refresh_market(force=True)
    assert game.store.get_json("contracts") == original


@pytest.mark.asyncio
async def test_arrival_keeps_other_orders_and_vehicle_outage_keeps_payout(
    game,
):
    from unittest.mock import patch

    from app.domain.errors import CatalogueError
    from tests.test_game import first_berlin_contract

    trip = await game.dispatch(first_berlin_contract(game)["id"], "truck_01")
    remaining = game.store.get_json("contracts")
    trip["arrives_at"] = 0
    game.store.set_json("active_trips", [trip])
    cash = game.store.get_json("player")["cash"]
    with patch.object(
        game.market.vehicles,
        "list_models",
        side_effect=CatalogueError("offline"),
    ):
        assert game.reconcile_arrival()
        assert not game.reconcile_arrival()
    assert game.store.get_json("player")["cash"] == cash + trip["payout_eur"]
    assert game.store.get_json("contracts") == remaining
    refilled = game.refresh_market()
    assert refilled[: len(remaining)] == remaining
