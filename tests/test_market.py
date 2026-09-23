import random
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.api.v1.game_projection import (
    project_contract,
    project_transport,
)
from app.domain.contracts import ContractOffer, ContractOfferSnapshot
from app.domain.errors import WorldCatalogueError
from app.domain.game import OwnedVehicle
from app.domain.world import FacilityQuery
from app.services.contract_factory import ContractFactory
from app.services.market import MarketGenerator
from app.services.market_scope import MarketScopeResolver
from app.services.trade_network import TradeNetwork
from app.simulation import PayloadBand, build_payload_bands


def test_market_generate_guarantees_origin_and_real_addresses_are_external(
    world_catalogue,
    catalogue,
):
    market = MarketGenerator(world_catalogue, random.Random(3), catalogue)
    contracts = market.generate(1000, ["berlin_westhafen", "missing"], 4)
    snapshot = world_catalogue.read()
    berlin = snapshot.get_facility("berlin_westhafen")
    build_payload_bands(
        [model.capacity_tons for model in catalogue.list_models()]
    )
    assert len(contracts) == 4
    assert contracts[0].origin.facility_uid == berlin.facility_uid
    for contract in contracts:
        assert (
            contract.origin.facility_uid != contract.destination.facility_uid
        )
        assert contract.relationship_simulated is True
        assert contract.market_model == "nhm_v1"
        assert contract.cargo_system == "NHM2026"
        assert contract.origin.coordinate_evidence
        assert contract.destination.coordinate_evidence


def test_build_contract_has_expiry_and_valid_nhm_cargo(
    world_catalogue,
    catalogue,
):
    snapshot = world_catalogue.read()
    origin = snapshot.get_facility("berlin_westhafen")
    candidates = tuple(f for f in snapshot.facilities if f.is_routable())
    market = MarketGenerator(world_catalogue, random.Random(3), catalogue)
    network = TradeNetwork(candidates)
    options = network.options_for(origin.facility_uid)
    option = market._select_trade_option(options)
    contract = ContractFactory(market.rng).build(
        option,
        1000,
        PayloadBand("heavy", 24),
    )
    assert isinstance(contract, ContractOfferSnapshot)
    assert contract.expires_at == 22600
    assert contract.cargo.code == option.cargo.code
    assert contract.cargo.name == option.cargo.name
    assert 8 <= contract.tons <= 24
    assert contract.rate_eur_per_km_ton == 0.18
    assert contract.destination.facility_uid != origin.facility_uid
    assert contract.trade_match_type in {"exact", "ancestor"}
    with pytest.raises(FrozenInstanceError):
        setattr(contract, "tons", 1)

    payload = project_contract(contract)
    assert payload["cargo_code"] == option.cargo.code
    assert "cargo" not in payload["origin"]
    assert "handled_goods" not in payload["origin"]
    with pytest.raises(WorldCatalogueError):
        TradeNetwork._build_trade_options(
            replace(origin, cargo=()),
            {},
            {},
        )
    with pytest.raises(WorldCatalogueError):
        network.options_for("missing")


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
    contracts = market.generate(
        1000,
        [first.facility_uid, second.facility_uid],
        contract_count=3,
    )
    assert len(contracts) == 3
    assert {contract.origin.facility_uid for contract in contracts} == {
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
    origin_ids = [
        facility.facility_uid
        for facility in facilities
        if facility.is_routable()
    ]
    contracts = market.generate(1000, origin_ids)
    network = market.trade_network
    assert {contract.origin.facility_uid for contract in contracts} == {
        facility.facility_uid
        for facility in facilities
        if facility.is_routable()
    }
    assert all(contract.market_model == "nhm_v1" for contract in contracts)
    assert all(contract.cargo_system == "NHM2026" for contract in contracts)
    assert all(
        contract.cargo.code != "simulated_standard"
        and "Standardfracht" not in contract.cargo.name
        for contract in contracts
    )
    for contract in contracts:
        origin = contract.origin_cargo_evidence
        destination = contract.destination_cargo_evidence
        assert (
            origin.nhm_row_id in destination.ancestor_row_ids
            or destination.nhm_row_id in origin.ancestor_row_ids
        )
        assert contract.cargo_basis in {"documented", "derived"}
    remaining = contracts[1:]
    refilled = market.generate(
        1001,
        origin_ids,
        existing_contracts=remaining,
    )
    assert refilled[: len(remaining)] == remaining
    assert len(refilled) == len(contracts)
    assert refilled[-1].origin.facility_uid == contracts[0].origin.facility_uid
    assert (
        market.generate(1002, origin_ids, existing_contracts=refilled)
        == refilled
    )
    assert market.trade_network is network


def test_market_scope_combines_idle_trucks_and_zoomed_viewport(
    world_catalogue,
):
    resolver = MarketScopeResolver(world_catalogue)
    berlin = world_catalogue.read().get_facility("berlin_westhafen")
    vehicles = [
        OwnedVehicle.from_dict(
            {
                "id": "idle",
                "name": "Idle",
                "mode": "truck",
                "capacity_tons": 24,
                "hub_id": berlin.facility_uid,
                "facility_uid": berlin.facility_uid,
                "status": "idle",
            }
        ),
        OwnedVehicle.from_dict(
            {
                "id": "busy",
                "name": "Busy",
                "mode": "truck",
                "capacity_tons": 24,
                "hub_id": "ignored",
                "status": "enroute",
            }
        ),
    ]
    query = FacilityQuery.parse("-10,35,30,60")

    low_zoom = resolver.resolve(vehicles, query, 6.99)
    assert low_zoom == (berlin.facility_uid,)

    high_zoom = resolver.resolve(
        vehicles,
        query,
        resolver.minimum_zoom,
    )
    assert berlin.facility_uid in high_zoom
    assert len(high_zoom) > len(low_zoom)
    assert resolver.resolve([], query, 6.99) == ()
    assert resolver.resolve(vehicles, query, float("nan")) == low_zoom


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
    facilities = tuple(
        facility
        for facility in world_catalogue.read().facilities
        if facility.is_routable()
    )
    origin_ids = [facility.facility_uid for facility in facilities]
    contracts = market.generate(1000, origin_ids)
    assert len(contracts) == len(facilities) * 3
    for facility in facilities:
        local = [
            contract
            for contract in contracts
            if contract.origin.facility_uid == facility.facility_uid
        ]
        assert {contract.payload_band for contract in local} == {
            "light",
            "medium",
            "heavy",
        }
        for capacity in capacities:
            assert any(0 < contract.tons <= capacity for contract in local)
        assert not all(contract.tons <= 1.1 for contract in local)
    legacy = replace(contracts[0], id="unchanged", tons=24, payload_band="")
    retained = [legacy, *contracts[1:]]
    refilled = market.generate(
        1001,
        origin_ids,
        existing_contracts=retained,
    )
    assert refilled[: len(retained)] == retained
    assert len(refilled) == len(contracts) + 1
    vehicles.list_models.return_value = [SimpleNamespace(capacity_tons=0.01)]
    tiny = market.generate(
        1002,
        origin_ids,
        existing_contracts=refilled,
    )
    assert len(
        [contract for contract in tiny if contract.tons == 0.01]
    ) == len(facilities)
    vehicles.list_models.return_value = [SimpleNamespace(capacity_tons=24)]
    legacy_fleet = market.generate(
        1003,
        origin_ids,
        owned_capacities=[12],
    )
    assert len(legacy_fleet) == len(facilities) * 2
    assert {contract.payload_band for contract in legacy_fleet} == {
        "medium",
        "heavy",
    }


def test_vehicle_catalogue_outage_preserves_only_current_market(
    game, monkeypatch
):
    from app.domain.errors import CatalogueError

    original = game.refresh_market()
    legacy = replace(
        original[0], id="legacy-generic", market_model="previous-market"
    )
    game.state_repository.replace_offers((legacy, *original))
    monkeypatch.setattr(
        game.market.vehicles,
        "list_models",
        Mock(side_effect=CatalogueError("offline")),
    )
    surviving = [project_contract(value) for value in game.refresh_market()]
    assert all(item.get("market_model") == "nhm_v1" for item in surviving)
    assert all(item["id"] != "legacy-generic" for item in surviving)
    assert [
        project_contract(item) for item in game.state_repository.list_offers()
    ] == surviving

    listed = [project_contract(value) for value in game.list_contracts()]
    assert [item["id"] for item in listed] == [
        item["id"] for item in surviving
    ]

    with pytest.raises(CatalogueError, match="offline"):
        [project_contract(value) for value in game.refresh_market(force=True)]


@pytest.mark.asyncio
async def test_arrival_keeps_other_orders_and_vehicle_outage_keeps_payout(
    monkeypatch,
    game,
):
    from unittest.mock import patch

    from app.domain.errors import CatalogueError
    from tests.test_game import first_berlin_contract

    trip = project_transport(
        await game.dispatch(first_berlin_contract(game)["id"], "truck_01")
    )
    remaining = [
        project_contract(item) for item in game.state_repository.list_offers()
    ]
    monkeypatch.setattr(game, "now", lambda: trip["arrives_at"] + 1)
    cash = game._get_player().to_dict()["cash"]
    with patch.object(
        game.market.vehicles,
        "list_models",
        side_effect=CatalogueError("offline"),
    ):
        assert game.reconcile_arrival()
        assert not game.reconcile_arrival()
    assert game._get_player().to_dict()["cash"] == cash + trip["payout_eur"]
    assert [
        project_contract(item) for item in game.state_repository.list_offers()
    ] == []
    refilled = [project_contract(value) for value in game.refresh_market()]
    assert refilled
    destination_id = trip["contract"]["destination_hub_id"]
    assert {item["origin_hub_id"] for item in refilled} == {destination_id}
    previous_ids = {item["id"] for item in remaining}
    assert all(item["id"] not in previous_ids for item in refilled)


def test_market_generation_never_serializes_domain_objects(game):
    origin = game.state_repository.list_vehicles()[0].hub_id
    with (
        patch(
            "app.api.v1.game_projection.project_contract",
            side_effect=AssertionError("snapshot serialization"),
        ),
        patch(
            "app.repositories.snapshot_mapping.load_offer",
            side_effect=AssertionError("offer serialization"),
        ),
    ):
        offers = game.market.generate(1000, [origin])
        assert all(isinstance(offer, ContractOffer) for offer in offers)
        assert (
            game.market.generate(1001, [origin], existing_contracts=offers)
            == offers
        )
        assert game.market.generate(1001, ["unknown"]) == []
