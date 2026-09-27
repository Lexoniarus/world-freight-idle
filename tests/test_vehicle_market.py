"""Vehicle-ready coverage shares offers and never substitutes city totals."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.domain.contracts import ContractOffer
from app.services.market_scope import MarketScopeResolver
from app.services.vehicle_coverage import vehicle_candidates, vehicle_offers
from tests.test_market import city_market as city_market
from tests.test_market_preparation import bind_preparation, make_batch


def test_vehicle_coverage_fills_small_vehicle_after_city_is_full(city_market):
    market, owned, fleet, _, _ = city_market
    city = owned.location.city.city_uid
    large = fleet[0]
    small = replace(large, vehicle_id="small", capacity_tons=1)
    original, _ = market.generate(1, (city,), fleet)
    assert len(original) == 9
    assert not any(offer.tons <= 1 for offer in original)
    fleet = (large, small)
    candidates = market.candidates.build((city,), fleet)
    offers, _ = market.generate(2, (city,), fleet, original)
    usable = vehicle_offers(offers, small, candidates)
    assert len(usable) == 9
    assert all(offer.tons <= 1 for offer in usable)
    assert len(offers) == 18
    assert market.generate(3, (city,), fleet, offers)[0] == offers
    diagnostic = market.vehicle_coverage.diagnose(
        small, candidates, candidates, offers
    )
    assert diagnostic.distance_counts == (3, 3, 3)
    assert diagnostic.unmet_bands == ()
    assert diagnostic.unmet_facilities == ()
    assert len(vehicle_offers(offers, large, candidates)) == 18


def test_shared_planned_offers_cover_identical_vehicles_once(city_market):
    market, owned, fleet, _, _ = city_market
    other = replace(fleet[0], vehicle_id="other")
    fleet = (*fleet, other)
    city = owned.location.city.city_uid
    offers, _ = market.generate(1, (city,), fleet)
    candidates = market.candidates.build((city,), fleet)
    assert len(offers) == 9
    assert all(len(vehicle_offers(offers, v, candidates)) == 9 for v in fleet)
    assert (
        vehicle_candidates(candidates, replace(other, vehicle_id="absent"))
        == ()
    )
    short = tuple(
        c for c in candidates if c.distance_profile.distance_band == "short"
    )
    partial, _ = market.generate(2, (city,), fleet, (), short)
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
    game.market_lifecycle.generator = market
    game.market_lifecycle.scope = game.market_scope
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
    readiness = preparation.readiness
    for candidate in (at_pickup, remote):
        await readiness.prepare(
            candidate.trade.origin.facility_uid,
            candidate.trade.destination.facility_uid,
        )
    ready = preparation.ready_candidates((at_pickup, remote))
    assert len(ready) == 1 and ready[0].trade == at_pickup.trade
    approach = await readiness.prepare(
        fleet[0].facility_uid, remote.trade.origin.facility_uid
    )
    assert approach is not None
    assert len(preparation.ready_candidates((at_pickup, remote))) == 2
    offers = game.refresh_market()
    assert game.contract_choices(offers, fleet[0].vehicle_id)
    with patch.object(
        readiness.store, "payload", wraps=readiness.store.payload
    ) as payload:
        payload.side_effect = lambda ref: (
            None if ref == approach.reference else payload._mock_wraps(ref)
        )
        scoped = game.contract_choices(offers, fleet[0].vehicle_id)
        assert all(
            item.offer.origin.facility_uid == fleet[0].facility_uid
            for item in scoped
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


@pytest.mark.asyncio
async def test_worker_completes_vehicle_gaps_and_exhausts_failed_approaches(
    vehicle_game,
):
    game, preparation = vehicle_game
    batch = make_batch(game, preparation)
    first = await batch.process()
    for _ in range(10):
        first = await batch.process()
        if first.status == "ready":
            break
    assert first.status == "ready"
    vehicle = game.get_vehicle("truck")
    original = game.list_contracts()
    assert len(original) == 9
    # Keep the large offers but shrink this owned vehicle's capacity.
    vehicle._capacity_tons = 1
    game.state_repository.save_vehicle(vehicle)
    result = await batch.process()
    for _ in range(10):
        result = await batch.process()
        if result.status == "ready":
            break
    assert result.status == "ready"
    assert all(
        item.offer.tons <= 1
        for item in game.contract_choices(game.list_contracts(), "truck")
    )
    # Simulate a deterministic failure for every remaining approach.
    readiness = preparation.readiness
    existing = readiness.current

    def failed(origin, destination):
        relation = existing(origin, destination)
        if origin == vehicle.facility_uid and destination == "origin-b":
            assert relation is not None
            return replace(
                relation,
                status="deterministic_failure",
                failure_category="no_path",
            )
        return relation

    with patch.object(readiness, "current", side_effect=failed):
        result = await batch.process()
        for _ in range(3):
            result = await batch.process()
        assert result.status == "exhausted"
        diagnostic = game.vehicle_coverage()[0]
        assert diagnostic.unmet_facilities == ("origin-b",)
        assert all(
            item.offer.origin.facility_uid == vehicle.facility_uid
            for item in game.contract_choices(game.list_contracts(), "truck")
        )


@pytest.mark.asyncio
async def test_departure_during_preparation_cannot_publish_stale_vehicle_coverage(
    vehicle_game,
):
    game, preparation = vehicle_game
    batch = make_batch(game, preparation)

    async def departure(*args):
        vehicle = game.get_vehicle("truck")
        vehicle.start_trip()
        game.state_repository.save_vehicle(vehicle)
        return True, None

    with patch.object(preparation, "prepare_batch", side_effect=departure):
        result = await batch.process()
    assert result.status == "partial"
    assert game.list_contracts() == []
    assert game.vehicle_coverage() == ()
    with pytest.raises(ValueError, match="Fahrzeug"):
        game.contract_choices([], "truck")


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
            game.market_lifecycle.preparation, "retained", return_value=True
        ),
        patch.object(
            game.market_lifecycle.preparation,
            "eligible",
            side_effect=lambda o, f, s: sets[o.id],
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
    batch = make_batch(game, preparation)
    for _ in range(10):
        result = await batch.process()
        if result.status == "ready":
            break
    response = list_contracts(vehicle_id="truck", game=game)
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


def test_approaches_precede_delivery_batches_without_starvation(city_market):
    from app.domain.market_preparation import required_relations

    market, owned, fleet, _, _ = city_market
    candidates = market.candidates.build(
        (owned.location.city.city_uid,), fleet
    )
    pairs = required_relations(candidates)
    assert pairs[0] == (owned.facility_uid, "origin-b")
    assert len(pairs) == len(set(pairs))
