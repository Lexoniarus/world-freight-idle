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
    snapshot = world_catalogue.read()
    berlin = snapshot.get_facility("berlin_westhafen")
    bands = build_payload_bands(
        [model.capacity_tons for model in catalogue.list_models()]
    )
    assert len(contracts) == len(snapshot.facilities) * len(bands)
    assert contracts[0]["origin_facility_uid"] == berlin.facility_uid
    for contract in contracts:
        assert contract["origin_hub_id"] != contract["destination_hub_id"]
        assert contract["relationship_simulated"] is True
        assert contract["market_model"] == "nhm_v1"
        assert contract["cargo_system"] == "NHM2026"
        assert contract["origin"]["coordinate_evidence"]
        assert contract["destination"]["coordinate_evidence"]


def test_build_contract_has_expiry_and_valid_nhm_cargo(
    world_catalogue,
    catalogue,
):
    snapshot = world_catalogue.read()
    origin = snapshot.get_facility("berlin_westhafen")
    candidates = tuple(f for f in snapshot.facilities if f.is_routable())
    market = MarketGenerator(world_catalogue, random.Random(3), catalogue)
    inbound_by_row, inbound_by_ancestor = market._index_inbound_cargo(
        candidates
    )
    options = market._build_trade_options(
        origin,
        inbound_by_row,
        inbound_by_ancestor,
    )
    option = market._select_trade_option(options)
    contract = market._build_contract(
        option,
        1000,
        PayloadBand("heavy", 24),
    )
    assert contract["expires_at"] == 22600
    assert contract["cargo_code"] == option.cargo.code
    assert contract["cargo"] == option.cargo.name
    assert 8 <= contract["tons"] <= 24
    assert contract["rate_eur_per_km_ton"] == 0.18
    assert contract["destination_facility_uid"] != origin.facility_uid
    assert contract["trade_match_type"] in {"exact", "ancestor"}
    with pytest.raises(WorldCatalogueError):
        market._build_trade_options(origin, {}, {})


def test_market_contract_count_can_extend_small_valid_market(
    world_catalogue,
):
    snapshot = world_catalogue.read()
    terminals = tuple(
        facility
        for facility in snapshot.facilities
        if facility.facility_type == "intermodal_terminal"
    )
    first, second = terminals[:2]
    world = Mock(
        read=Mock(return_value=replace(snapshot, facilities=(first, second)))
    )
    vehicles = Mock(
        list_models=Mock(return_value=[SimpleNamespace(capacity_tons=24.0)])
    )
    market = MarketGenerator(world, random.Random(11), vehicles)
    contracts = market.generate(1000, [], contract_count=3)
    assert len(contracts) == 3
    assert {contract["origin_facility_uid"] for contract in contracts} == {
        first.facility_uid,
        second.facility_uid,
    }


def test_market_generate_rejects_world_without_onward_work(
    world_catalogue, catalogue
):
    snapshot = world_catalogue.read()
    world = Mock(read=Mock(return_value=replace(snapshot, facilities=())))
    with pytest.raises(WorldCatalogueError):
        MarketGenerator(world, random.Random(1), catalogue).generate(1, [])


def test_every_routable_facility_has_nhm_work_without_generic_freight(
    world_catalogue,
    catalogue,
):
    market = MarketGenerator(world_catalogue, random.Random(3), catalogue)
    facilities = world_catalogue.read().facilities
    contracts = market.generate(1000, ["berlin_westhafen", "berlin_westhafen"])
    assert {contract["origin_facility_uid"] for contract in contracts} == {
        facility.facility_uid
        for facility in facilities
        if facility.is_routable()
    }
    assert all(contract["market_model"] == "nhm_v1" for contract in contracts)
    assert all(contract["cargo_system"] == "NHM2026" for contract in contracts)
    assert all(
        contract["cargo_code"] != "simulated_standard"
        and "Standardfracht" not in contract["cargo"]
        for contract in contracts
    )
    for contract in contracts:
        origin = contract["origin_cargo_evidence"]
        destination = contract["destination_cargo_evidence"]
        assert (
            origin["nhm_row_id"] in destination["ancestor_row_ids"]
            or destination["nhm_row_id"] in origin["ancestor_row_ids"]
        )
        assert contract["cargo_basis"] in {"documented", "derived"}
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
    facilities = tuple(
        facility
        for facility in world_catalogue.read().facilities
        if facility.is_routable()
    )
    assert len(contracts) == len(facilities) * 3
    for facility in facilities:
        local = [
            contract
            for contract in contracts
            if contract["origin_hub_id"] == facility.facility_uid
        ]
        assert {contract["payload_band"] for contract in local} == {
            "light",
            "medium",
            "heavy",
        }
        for capacity in capacities:
            assert any(0 < contract["tons"] <= capacity for contract in local)
        assert not all(contract["tons"] <= 1.1 for contract in local)
    legacy = {**contracts[0], "id": "unchanged", "tons": 24}
    legacy.pop("payload_band")
    retained = [legacy, *contracts[1:]]
    refilled = market.generate(1001, [], existing_contracts=retained)
    assert refilled[: len(retained)] == retained
    assert len(refilled) == len(contracts) + 1
    vehicles.list_models.return_value = [SimpleNamespace(capacity_tons=0.01)]
    tiny = market.generate(1002, [], existing_contracts=refilled)
    assert len(
        [contract for contract in tiny if contract["tons"] == 0.01]
    ) == len(facilities)
    vehicles.list_models.return_value = [SimpleNamespace(capacity_tons=24)]
    legacy_fleet = market.generate(1003, [], owned_capacities=[12])
    assert len(legacy_fleet) == len(facilities) * 2
    assert {contract["payload_band"] for contract in legacy_fleet} == {
        "medium",
        "heavy",
    }


def test_vehicle_catalogue_outage_preserves_only_current_market(
    game, monkeypatch
):
    from app.domain.errors import CatalogueError

    original = game.refresh_market()
    legacy = dict(original[0])
    legacy["id"] = "legacy-generic"
    legacy.pop("market_model")
    game.store.set_json("contracts", [legacy, *original])
    monkeypatch.setattr(
        game.market.vehicles,
        "list_models",
        Mock(side_effect=CatalogueError("offline")),
    )
    surviving = game.refresh_market()
    assert all(item.get("market_model") == "nhm_v1" for item in surviving)
    assert all(item["id"] != "legacy-generic" for item in surviving)
    assert game.store.get_json("contracts") == surviving
    with pytest.raises(CatalogueError, match="offline"):
        game.refresh_market(force=True)


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
