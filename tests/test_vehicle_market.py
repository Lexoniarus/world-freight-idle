"""Vehicle-ready coverage shares offers and never substitutes city totals."""

from dataclasses import replace
from itertools import cycle, islice
from unittest.mock import Mock, patch

import pytest

from app.domain.contracts import ContractOffer
from app.domain.market import MarketCandidate
from app.services.dispatch_eligibility import DispatchEligibilityService
from app.services.market_scope import MarketScopeResolver
from app.services.vehicle_coverage import vehicle_candidates, vehicle_offers
from tests.support.market import bind_preparation, make_stock_batch
from tests.test_market import city_market as city_market


def select_three_per_distance_band(
    candidates: tuple[MarketCandidate, ...],
) -> tuple[MarketCandidate, ...]:
    """Repeat valid relations only when a band has fewer than three."""
    selected = []
    for band in ("short", "medium", "long"):
        choices = tuple(
            candidate
            for candidate in candidates
            if candidate.distance_profile.distance_band == band
        )
        selected.extend(islice(cycle(choices), 3))
    return tuple(selected)


def test_vehicle_coverage_reports_only_materialized_vehicle_stock(city_market):
    market, owned, fleet, _, _ = city_market
    city = owned.location.city.city_uid
    large = fleet[0]
    small = replace(large, vehicle_id="small", capacity_tons=1)
    fleet = (large, small)
    candidates = market.candidates.build((city,), fleet)
    pool = vehicle_candidates(candidates, small)
    selected = select_three_per_distance_band(pool)
    offers = tuple(
        ContractOffer.from_snapshot(
            market.factory.build(candidate, 2, f"small:{index}")
        )
        for index, candidate in enumerate(selected)
    )
    usable = vehicle_offers(offers, small, candidates)
    assert len(usable) == 9
    assert all(offer.tons <= 1 for offer in usable)
    diagnostic = market.vehicle_coverage.diagnose(
        small, candidates, candidates, offers
    )
    assert diagnostic.distance_counts == (3, 3, 3)
    assert diagnostic.unmet_bands == ()
    assert diagnostic.unmet_facilities == ()
    assert len(vehicle_offers(offers, large, candidates)) == 9


def test_shared_materialized_offers_cover_identical_vehicles_once(city_market):
    market, owned, fleet, _, _ = city_market
    other = replace(fleet[0], vehicle_id="other")
    fleet = (*fleet, other)
    city = owned.location.city.city_uid
    candidates = market.candidates.build((city,), fleet)
    selected = select_three_per_distance_band(candidates)
    offers = tuple(
        ContractOffer.from_snapshot(
            market.factory.build(candidate, 1, f"shared:{index}")
        )
        for index, candidate in enumerate(selected)
    )
    assert all(len(vehicle_offers(offers, v, candidates)) == 9 for v in fleet)
    assert (
        vehicle_candidates(candidates, replace(other, vehicle_id="absent"))
        == ()
    )
    short = tuple(
        c for c in candidates if c.distance_profile.distance_band == "short"
    )
    partial = tuple(
        ContractOffer.from_snapshot(
            market.factory.build(candidate, 2, f"short:{index}")
        )
        for index, candidate in enumerate(short[:3])
    )
    diagnostic = market.vehicle_coverage.diagnose(
        other, candidates, short, partial
    )
    assert diagnostic.distance_counts == (3, 0, 0)
    assert diagnostic.unmet_bands == ("medium", "long")


@pytest.fixture
def vehicle_game(game, city_market, database):
    market, owned, _, world, _ = city_market
    with database.transaction(), database.connect() as connection:
        connection.execute("DELETE FROM contract_offers")
        connection.execute("DELETE FROM owned_vehicles")
        game.state_repository.save_vehicle(owned)
    game.world = world
    game.market = market
    game.market_scope = MarketScopeResolver(world)
    game.market_lifecycle.market = market
    game.market_lifecycle.scope = game.market_scope
    game.transport_dispatch.eligibility = DispatchEligibilityService(
        market.candidates
    )
    preparation = bind_preparation(game, database)
    return game, preparation


@pytest.mark.asyncio
async def test_vehicle_readiness_requires_approach_and_excludes_stale(
    vehicle_game,
):
    game, preparation = vehicle_game
    fleet = game.market.candidates.resolve_fleet(
        game.state_repository.list_vehicles()
    )
    candidates = game.market.candidates.build((fleet[0].city_uid,), fleet)
    at_pickup = next(
        c
        for c in candidates
        if c.trade.origin.facility_uid == fleet[0].facility_uid
    )
    remote = next(
        c
        for c in candidates
        if c.trade.origin.facility_uid != fleet[0].facility_uid
    )
    readiness = preparation.routes.readiness
    for candidate in (at_pickup, remote):
        await readiness.prepare(
            candidate.trade.origin.facility_uid,
            candidate.trade.destination.facility_uid,
        )
    ready = preparation.routes.ready_candidates((at_pickup, remote))
    assert len(ready) == 1 and ready[0].trade == at_pickup.trade
    approach = await readiness.prepare(
        fleet[0].facility_uid, remote.trade.origin.facility_uid
    )
    assert approach is not None
    ready = preparation.routes.ready_candidates((at_pickup, remote))
    assert len(ready) == 2
    offers = tuple(
        ContractOffer.from_snapshot(game.market.factory.build(item, 1))
        for item in ready
    )
    game.state_repository.replace_offers(offers)
    preparation.routes.bind(offers)
    offers = game.list_contracts()
    assert game.contract_choices(offers, fleet[0].vehicle_id)
    with patch.object(
        readiness.store,
        "payload",
        wraps=readiness.store.payload,
    ) as payload:
        payload.side_effect = lambda ref: (
            None if ref == approach.reference else payload._mock_wraps(ref)
        )
        scoped = game.contract_choices(offers, fleet[0].vehicle_id)
        assert any(
            item.offer.origin.facility_uid != fleet[0].facility_uid
            for item in scoped
        )
        with pytest.raises(ValueError, match="vorbereitet"):
            readiness.load(
                fleet[0].facility_uid,
                remote.trade.origin.facility_uid,
            )
    readiness.provider_identity = "changed"
    assert game.contract_choices(offers, fleet[0].vehicle_id) == ()
    with pytest.raises(ValueError, match="vorbereitet"):
        readiness.load(
            remote.trade.origin.facility_uid,
            remote.trade.destination.facility_uid,
        )
    with pytest.raises(ValueError, match="Fahrzeug"):
        game.contract_choices(offers, "foreign")


def test_two_vehicle_projection_uses_authoritative_sets(vehicle_game):
    game, _ = vehicle_game
    # Verify projection independently of materialization and HTTP formatting.
    owned = game.get_vehicle("truck")
    from app.services.fleet import build_owned_vehicle

    model = game.market.candidates.catalogue.list_models()[0]
    other = build_owned_vehicle(model, "second", owned.location)
    game.state_repository.save_vehicle(other)
    fleet = game.market.candidates.resolve_fleet((owned, other))
    pool = game.market.candidates.build((fleet[0].city_uid,), fleet)
    offers = tuple(
        ContractOffer.from_snapshot(game.market.factory.build(pool[0], 1))
        for _ in range(3)
    )
    sets = {
        offers[0].id: ("truck", "second"),
        offers[1].id: ("truck",),
        offers[2].id: ("second",),
    }
    with (
        patch.object(
            type(game.market_lifecycle.routes),
            "matches_snapshot",
            lambda self, offer, snapshot: True,
        ),
        patch.object(
            type(game.market_lifecycle.routes),
            "eligible_from_snapshot",
            lambda self, offer, fleet, structural, snapshot: sets[offer.id],
        ),
    ):
        assert [
            x.offer.id for x in game.contract_choices(offers, "truck")
        ] == [offers[0].id, offers[1].id]
        assert [
            x.offer.id for x in game.contract_choices(offers, "second")
        ] == [offers[0].id, offers[2].id]


@pytest.mark.asyncio
async def test_vehicle_projection_api_enforces_owned_idle_selection(
    vehicle_game,
):
    from fastapi import HTTPException

    from app.api.v1.contracts import list_contracts, refresh_contracts

    game, preparation = vehicle_game
    batch = make_stock_batch(game, preparation)
    preparation.demand.request()
    for _ in range(100):
        result = await batch.process()
        if result.status == "ready":
            break
    with (
        patch.object(
            preparation.routes.references,
            "get_many",
            wraps=preparation.routes.references.get_many,
        ) as get_many,
        patch.object(
            preparation.routes.references,
            "get",
            side_effect=AssertionError("Market reads must be set-based"),
        ),
    ):
        response = list_contracts(vehicle_id="truck", game=game)
    get_many.assert_called_once()
    assert response["contracts"]
    assert all(
        "truck" in o["eligible_vehicle_ids"] for o in response["contracts"]
    )
    assert response["vehicle_coverage"][0]["vehicle_id"] == "truck"
    assert response["vehicle_coverage"][0]["unmet_bands"] == ()
    refreshed = refresh_contracts(vehicle_id="truck", game=game)
    assert len(refreshed["contracts"]) == 9
    for value in ("foreign", ""):
        with pytest.raises(HTTPException) as failure:
            list_contracts(vehicle_id=value, game=game)
        assert failure.value.status_code == 400
    vehicle = game.get_vehicle("truck")
    vehicle.start_trip()
    game.state_repository.save_vehicle(vehicle)
    with pytest.raises(HTTPException) as failure:
        list_contracts(vehicle_id="truck", game=game)
    assert failure.value.status_code == 400


def test_market_refresh_maps_only_client_errors_to_http():
    from fastapi import HTTPException

    from app.api.v1.contracts import refresh_contracts
    from app.domain.errors import CatalogueError

    game = Mock()
    game.read_market.side_effect = ValueError("invalid scope")
    with pytest.raises(HTTPException) as failure:
        refresh_contracts(vehicle_id="truck", game=game)
    assert failure.value.status_code == 400

    game.read_market.side_effect = CatalogueError("catalogue unavailable")
    with pytest.raises(CatalogueError, match="catalogue unavailable"):
        refresh_contracts(vehicle_id="truck", game=game)


def test_approaches_precede_delivery_batches_without_starvation(city_market):
    from app.domain.market_preparation import required_relations

    market, owned, fleet, _, _ = city_market
    candidates = market.candidates.build(
        (owned.location.city.city_uid,), fleet
    )
    pairs = required_relations(candidates)
    assert pairs[0] == (owned.facility_uid, "origin-b")
    assert len(pairs) == len(set(pairs))
