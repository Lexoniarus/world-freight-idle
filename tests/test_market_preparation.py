"""Publication and dispatch consume readiness without provider fallbacks."""

import asyncio
from dataclasses import replace
from typing import TypeVar
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.errors import RoutingError
from app.repositories.cached_world_catalogue import CachedWorldCatalogue
from app.repositories.market_preparation import SqlitePreparationStore
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_readiness import (
    SqliteOfferRouteStore,
    SqliteRoutingReadinessStore,
)
from app.services.market_preparation import MarketPreparationService
from app.services.preparation_batch import MarketPreparationBatchService
from app.services.preparation_worker import MarketPreparationWorker
from app.services.routing_readiness import RoutingReadinessService
from tests.conftest import FakeRouter, FakeRoutingAnchorResolver

T = TypeVar("T")


def require_value(value: T | None) -> T:
    assert value is not None
    return value


def make_batch(game, preparation):
    return MarketPreparationBatchService(
        game.state_repository,
        game.market.candidates,
        game.market.coverage,
        game.market_scope,
        preparation,
        game.market_lifecycle.refresh,
        game.market.vehicle_coverage,
    )


def bind_preparation(game, database):
    game.world = CachedWorldCatalogue(game.world)
    game.market.candidates.world = game.world
    SqliteProviderCache(database)
    store = SqliteRoutingReadinessStore(database)
    jobs = SqlitePreparationStore(database)
    anchor_store = SqliteRoutingAnchorRepository(database)
    readiness = RoutingReadinessService(
        store,
        FakeRoutingAnchorResolver(),
        anchor_store,
        FakeRouter(),
        CachedWorldCatalogue(game.world),
        "test-provider",
        game.now,
    )
    preparation = MarketPreparationService(
        "test-owner",
        readiness,
        SqliteOfferRouteStore(database, "test-owner"),
        jobs,
        game.now,
        database,
    )
    game.market_lifecycle.preparation = preparation
    game.dispatch_planning.preparation = preparation
    return preparation


@pytest.mark.asyncio
async def test_partial_market_never_publishes_unchecked_offers(game, database):
    preparation = bind_preparation(game, database)
    assert game.refresh_market() == []
    owned = game.state_repository.list_vehicles()
    fleet = game.market.candidates.resolve_fleet(owned)
    pool = game.market.candidates.build(
        game.market_scope.resolve(owned), fleet
    )
    candidate = pool[0]
    origin = candidate.trade.origin.facility_uid
    destination = candidate.trade.destination.facility_uid
    readiness = preparation.readiness
    assert readiness.ready(origin, destination) is None
    with pytest.raises(ValueError, match="vorbereitet"):
        readiness.load(origin, destination)
    result = require_value(await readiness.prepare(origin, destination))
    # Delivery alone cannot publish an offer for an unprepared approach.
    if owned[0].facility_uid != origin:
        assert game.refresh_market() == []
        await readiness.prepare(owned[0].facility_uid, origin)
    assert result.status == "ready"
    readiness.router = AsyncMock()
    assert await readiness.prepare(origin, destination) == result
    readiness.router.route.assert_not_called()
    offers = game.refresh_market()
    assert offers
    assert all(preparation.retained(o) for o in offers)
    assert all(o.destination.facility_uid == destination for o in offers)
    offer = offers[0]
    vehicle = owned[0]
    readiness.router = AsyncMock()
    choices = game.contract_choices((offer,))
    assert vehicle.id in choices[0].eligible_vehicle_ids
    quote = await game.quote_contract(offer.id, vehicle.id)
    assert (
        quote.dispatch_route.delivery
        == readiness.load(origin, destination).to_snapshot()
    )
    trip = await game.dispatch(offer.id, vehicle.id)
    assert trip.origin == offer.origin
    assert preparation.references.get(offer.id) is None
    readiness.router.route.assert_not_called()


@pytest.mark.asyncio
async def test_stale_approach_requeues_completed_player_demand(game, database):
    preparation = bind_preparation(game, database)
    owned = game.state_repository.list_vehicles()
    fleet = game.market.candidates.resolve_fleet(owned)
    pool = game.market.candidates.build(
        game.market_scope.resolve(owned), fleet
    )
    candidate = next(
        item
        for item in pool
        if item.trade.origin.facility_uid != owned[0].facility_uid
    )
    origin = candidate.trade.origin.facility_uid
    destination = candidate.trade.destination.facility_uid
    readiness = preparation.readiness
    await readiness.prepare(origin, destination)
    approach = require_value(
        await readiness.prepare(owned[0].facility_uid, origin)
    )
    preparation.prepare_publication((candidate,), fleet)
    status = require_value(preparation.jobs.status("test-owner"))
    preparation.jobs.finish(
        "test-owner", status.generation, "ready", None, game.now()
    )
    with database.connect() as conn:
        conn.execute(
            "DELETE FROM route_cache WHERE cache_key IN "
            "(SELECT cache_key FROM routing_relations WHERE relation_id=?)",
            (approach.reference.relation_id,),
        )
    assert readiness.ready(origin, destination) is not None
    assert preparation.prepare_publication((candidate,), fleet) == ()
    updated = require_value(preparation.jobs.status("test-owner"))
    assert updated.generation != status.generation
    assert updated.status == "partial"
    assert preparation.jobs.next_player(game.now()) == "test-owner"


@pytest.mark.asyncio
async def test_global_negative_cache_timeout_and_stale_payload(game, database):
    preparation = bind_preparation(game, database)
    readiness = preparation.readiness
    offer = game.state_repository.list_offers()[0]
    pair = (offer.origin.facility_uid, offer.destination.facility_uid)
    error = RoutingError("No path")
    error.category = "no_path"
    readiness.router = AsyncMock()
    readiness.router.route.side_effect = error
    failure = require_value(await readiness.prepare(*pair))
    assert failure.status == "deterministic_failure"
    assert await readiness.prepare(*pair) == failure
    assert readiness.router.route.await_count == 1
    readiness.provider_identity = "changed-provider"
    error.category = "provider_unavailable"
    transient = require_value(await readiness.prepare(*pair))
    assert transient.retry_at is not None
    assert await readiness.prepare(*pair) == transient
    readiness.provider_identity = "recovered-provider"
    readiness.router = FakeRouter()
    ready = require_value(await readiness.prepare(*pair))
    with database.connect() as conn:
        conn.execute("DELETE FROM route_cache")
    assert readiness.ready(*pair) is None
    assert readiness.store.payload(ready.reference) is None
    readiness.timeout = 0.001

    async def slow_route(*args):
        await asyncio.sleep(1)

    readiness.router = AsyncMock()
    readiness.router.route.side_effect = slow_route
    timeout = require_value(await readiness.prepare(*pair))
    assert timeout.status == "transient_failure"
    with pytest.raises(ValueError):
        RoutingReadinessService(
            readiness.store,
            readiness.anchors,
            readiness.anchor_store,
            readiness.router,
            game.world,
            "test",
            game.now,
            0,
        )


@pytest.mark.asyncio
async def test_players_share_one_provider_calculation(game, database):
    preparation = bind_preparation(game, database)
    readiness = preparation.readiness
    offer = game.state_repository.list_offers()[0]
    pair = offer.origin.facility_uid, offer.destination.facility_uid
    entered = asyncio.Event()
    release = asyncio.Event()
    router = FakeRouter()

    async def route(*args):
        entered.set()
        await release.wait()
        return await router.route(*args)

    readiness.router = AsyncMock()
    readiness.router.route.side_effect = route
    first = asyncio.create_task(readiness.prepare(*pair))
    await entered.wait()
    assert await readiness.prepare(*pair) is None
    release.set()
    assert require_value(await first).status == "ready"
    assert readiness.router.route.await_count == 1


@pytest.mark.asyncio
async def test_worker_fills_ready_market_and_owns_shutdown(game, database):
    preparation = bind_preparation(game, database)
    game.refresh_market()
    worker = MarketPreparationWorker(
        preparation.jobs, lambda user: make_batch(game, preparation), game.now
    )
    assert preparation.jobs.next_player(game.now()) == "test-owner"
    for _ in range(30):
        await worker.process("test-owner")
        if (
            require_value(preparation.jobs.status("test-owner")).status
            == "ready"
        ):
            break
    assert (
        require_value(preparation.jobs.status("test-owner")).status == "ready"
    )
    assert game.list_contracts()
    assert all(
        o.eligible_vehicle_ids
        for o in game.contract_choices(game.list_contracts())
    )
    await worker.start()
    with pytest.raises(RuntimeError):
        await worker.start()
    await asyncio.sleep(1.05)
    await worker.close()
    await worker.close()


def test_preparation_generation_and_reference_rollback(game, database):
    preparation = bind_preparation(game, database)
    from app.domain.market_preparation import preparation_generation

    fleet = game.market.candidates.resolve_fleet(
        game.state_repository.list_vehicles()
    )
    first_generation = preparation_generation(fleet, (), ())
    assert preparation_generation(fleet, (), ()) == first_generation
    changed = (replace(fleet[0], capacity_tons=fleet[0].capacity_tons + 1),)
    assert preparation_generation(changed, (), ()) != first_generation
    assert preparation.jobs.status("missing") is None
    with pytest.raises(ValueError, match="publication"):
        preparation.bind(game.state_repository.list_offers())
    game.refresh_market()
    first = require_value(preparation.jobs.status("test-owner"))
    assert game.preparation_status() == first
    preparation.jobs.finish(
        "test-owner", "obsolete", "ready", None, game.now()
    )
    assert preparation.jobs.status("test-owner") == first
    preparation.jobs.finish(
        "test-owner", first.generation, "ready", None, game.now()
    )
    assert preparation.jobs.next_player(game.now()) is None
    preparation.jobs.request("test-owner", "new-generation", game.now())
    assert (
        require_value(preparation.jobs.status("test-owner")).status
        == "partial"
    )


def test_preparation_composition_preserves_unconfigured_test_runtime(
    game,
    runtime,
    database,
):
    from app.bootstrap import (
        build_market_preparation,
        build_preparation_worker,
    )

    assert build_market_preparation(runtime, "test-owner") is None
    preparation = bind_preparation(game, database)
    runtime.readiness = preparation.readiness
    runtime.preparation_jobs = preparation.jobs
    bound = require_value(build_market_preparation(runtime, "test-owner"))
    assert bound.user_id == "test-owner"
    worker = build_preparation_worker(runtime)
    assert (
        require_value(worker.batches("test-owner").preparation).user_id
        == "test-owner"
    )


@pytest.mark.asyncio
async def test_preparation_failures_backoff_fencing_and_worker_cleanup(
    game,
    database,
):
    preparation = bind_preparation(game, database)
    readiness = preparation.readiness
    owned = game.state_repository.list_vehicles()
    fleet = game.market.candidates.resolve_fleet(owned)
    pool = game.market.candidates.build(
        game.market_scope.resolve(owned), fleet
    )
    candidate = pool[0]
    pair = (
        candidate.trade.origin.facility_uid,
        candidate.trade.destination.facility_uid,
    )
    failed_anchor = await readiness.anchors.resolve(candidate.trade.origin)
    readiness.anchors = AsyncMock()
    readiness.anchors.resolve.return_value = replace(
        failed_anchor, anchor=None, validation_status="provider_unavailable"
    )
    transient = require_value(await readiness.prepare(*pair))
    assert transient.status == "transient_failure"
    complete, retry = await preparation.prepare_batch((candidate,), fleet)
    assert not complete and retry is not None
    readiness.provider_identity = "retry-generation"
    readiness.anchors = FakeRoutingAnchorResolver()
    with patch.object(readiness.store, "publish", return_value=False):
        assert await readiness.prepare(*pair) is None
        error = RoutingError("endpoint")
        error.category = "endpoint_unreachable"
        readiness.router = AsyncMock()
        readiness.router.route.side_effect = error
        assert await readiness.prepare(*pair) is None
        assert readiness.router.route.await_count == 2
    with patch.object(readiness, "prepare", return_value=None):
        complete, retry = await preparation.prepare_batch((candidate,), fleet)
        assert not complete and retry is not None
    readiness.router = FakeRouter()
    with patch.object(readiness.store, "renew", return_value=False):
        assert await readiness.prepare(*pair) is None
    game.refresh_market()
    worker = MarketPreparationWorker(
        preparation.jobs, lambda user: make_batch(game, preparation), game.now
    )
    with patch.object(worker, "process", side_effect=RuntimeError("batch")):
        await worker.start()
        await asyncio.sleep(0.01)
        await worker.close()
    assert (
        require_value(preparation.jobs.status("test-owner")).next_retry_at
        is not None
    )
    failed_worker = MarketPreparationWorker(
        preparation.jobs, lambda user: make_batch(game, preparation), game.now
    )
    with patch.object(
        preparation.jobs, "next_player", side_effect=RuntimeError("startup")
    ):
        await failed_worker.start()
        assert failed_worker._task is not None
        assert not failed_worker._task.done()
        await failed_worker.close()


@pytest.mark.asyncio
async def test_route_publication_rechecks_inputs_after_provider_await(
    game, database
):
    preparation = bind_preparation(game, database)
    readiness = preparation.readiness
    offer = game.state_repository.list_offers()[0]
    pair = offer.origin.facility_uid, offer.destination.facility_uid
    original = readiness.world.read()
    changed = replace(original, facilities=original.facilities[:-1])
    with patch.object(
        readiness.world, "read", side_effect=[original, changed]
    ):
        assert await readiness.prepare(*pair) is None
    router = FakeRouter()

    async def changes_during_success(*args):
        readiness.provider_identity = "changed-during-success"
        return await router.route(*args)

    readiness.router = AsyncMock()
    readiness.router.route.side_effect = changes_during_success
    assert await readiness.prepare(*pair) is None

    async def changes_during_failure(*args):
        readiness.provider_identity = "changed-during-failure"
        raise RoutingError("outage during revision change")

    readiness.router.route.side_effect = changes_during_failure
    assert await readiness.prepare(*pair) is None
    assert readiness.current(*pair) is None


@pytest.mark.asyncio
async def test_observed_global_graph_revision_invalidates_shared_routes(
    game, database
):
    from functools import partial

    preparation = bind_preparation(game, database)
    readiness = preparation.readiness
    store = SqliteRoutingReadinessStore(database)
    readiness.provider_revision = partial(store.provider_revision, "test")
    assert store.provider_revision("test") is None
    offer = game.state_repository.list_offers()[0]
    pair = offer.origin.facility_uid, offer.destination.facility_uid
    first = require_value(await readiness.prepare(*pair))
    store.observe_provider_revision("test", "graph-2")
    assert require_value(readiness.current(*pair)).status == "stale"
    assert readiness.ready(*pair) is None
    second = require_value(await readiness.prepare(*pair))
    assert first.reference != second.reference
    assert store.provider_revision("test") == "graph-2"


@pytest.mark.asyncio
async def test_ready_startup_rolls_back_all_players_and_references(
    game, runtime, database
):
    from app.bootstrap import build_market_startup

    preparation = bind_preparation(game, database)
    runtime.readiness = preparation.readiness
    runtime.preparation_jobs = preparation.jobs
    offer = game.state_repository.list_offers()[0]
    await preparation.readiness.prepare(
        offer.origin.facility_uid, offer.destination.facility_uid
    )
    for vehicle in game.state_repository.list_vehicles():
        if vehicle.facility_uid != offer.origin.facility_uid:
            await preparation.readiness.prepare(
                vehicle.facility_uid, offer.origin.facility_uid
            )
    original = tuple(game.refresh_market())
    assert original
    references = tuple(preparation.references.get(o.id) for o in original)
    with database.connect() as conn:
        conn.execute("INSERT INTO users VALUES ('z-owner','Second','hash',0)")
        conn.execute("INSERT INTO player_states VALUES ('z-owner',0,0,0)")
    startup = build_market_startup(runtime)
    factory = startup.lifecycle

    def fail_second(owner):
        if owner == "z-owner":
            raise RuntimeError("second account")
        return factory(owner)

    preparation.readiness.router = AsyncMock()
    with patch.object(startup, "lifecycle", side_effect=fail_second):
        with pytest.raises(RuntimeError, match="second account"):
            startup.rebuild()
    assert game.state_repository.list_offers() == original
    assert (
        tuple(preparation.references.get(o.id) for o in original) == references
    )
    startup.rebuild()
    assert game.state_repository.list_offers() != original
    assert all(
        preparation.retained(o) for o in game.state_repository.list_offers()
    )
    preparation.readiness.router.route.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_rejects_retired_and_changed_prepared_routes(
    game, database
):
    preparation = bind_preparation(game, database)
    owned = game.state_repository.list_vehicles()
    fleet = game.market.candidates.resolve_fleet(owned)
    candidates = game.market.candidates.build(
        game.market_scope.resolve(owned), fleet
    )
    candidate = next(
        item
        for item in candidates
        if item.trade.origin.facility_uid != owned[0].facility_uid
    )
    origin = candidate.trade.origin.facility_uid
    destination = candidate.trade.destination.facility_uid
    await preparation.readiness.prepare(origin, destination)
    await preparation.readiness.prepare(owned[0].facility_uid, origin)
    offer = game.refresh_market()[0]
    vehicle = owned[0]
    assert vehicle.location is not None
    planner = game.dispatch_planning
    route = await planner.route(vehicle.location, offer)
    with patch.object(preparation, "retained", return_value=False):
        assert game.contract_choices((offer,)) == ()
        with pytest.raises(ValueError, match="vorbereitet"):
            await planner.route(vehicle.location, offer)
        with pytest.raises(ValueError, match="geändert"):
            planner.quote(offer, route, vehicle, 1)
    changed_delivery = replace(
        route.delivery, distance_km=route.delivery.distance_km + 1
    )
    with pytest.raises(ValueError, match="Lieferroute"):
        planner.quote(
            offer, replace(route, delivery=changed_delivery), vehicle, 1
        )
    assert route.approach is not None
    changed_approach = replace(
        route.approach, distance_km=route.approach.distance_km + 1
    )
    with pytest.raises(ValueError, match="Anfahrtsroute"):
        planner.quote(
            offer, replace(route, approach=changed_approach), vehicle, 1
        )
