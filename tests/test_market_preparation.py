"""Publication and dispatch consume readiness without provider fallbacks."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.domain.errors import RoutingError
from app.repositories.routing_readiness import SqliteRoutingReadinessStore
from app.services.preparation_worker import (
    MarketPreparationWorker,
    PreparationWorkerTiming,
)
from app.services.routing_readiness import RoutingReadinessService
from tests.support.market import (
    build_prepared_game,
    make_stock_batch,
    require_value,
)
from tests.support.routing import FakeRouter, FakeRoutingAnchorResolver


@pytest.mark.asyncio
async def test_partial_market_never_publishes_unchecked_offers(game, database):
    game, preparation = build_prepared_game(game, database)
    batch = make_stock_batch(game, preparation)
    preparation.demand.ensure()
    assert game.list_contracts() == []
    owned = game.state_repository.list_vehicles()
    fleet = game.market.candidates.resolve_fleet(owned)
    pool = game.market.candidates.build(
        game.market_scope.resolve(owned), fleet
    )
    candidate = pool[0]
    origin = candidate.trade.origin.facility_uid
    destination = candidate.trade.destination.facility_uid
    readiness = preparation.routes.readiness
    assert readiness.ready(origin, destination) is None
    with pytest.raises(ValueError, match="vorbereitet"):
        readiness.load(origin, destination)
    result = require_value(await readiness.prepare(origin, destination))
    # Delivery alone cannot publish an offer for an unprepared approach.
    if owned[0].facility_uid != origin:
        assert game.list_contracts() == []
        await readiness.prepare(owned[0].facility_uid, origin)
    assert result.status == "ready"
    readiness.router = AsyncMock()
    assert await readiness.prepare(origin, destination) == result
    readiness.router.route.assert_not_called()
    for _ in range(30):
        await batch.process()
        if game.list_contracts():
            break
    offers = game.list_contracts()
    assert offers
    assert all(preparation.routes.retained_current(o) for o in offers)
    assert all(
        readiness.ready(o.origin.facility_uid, o.destination.facility_uid)
        for o in offers
    )
    offer = next(
        o for o in offers if o.destination.facility_uid == destination
    )
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
    assert preparation.routes.references.get(offer.id) is None
    readiness.router.route.assert_not_called()


@pytest.mark.asyncio
async def test_missing_payload_is_detected_only_when_geometry_is_loaded(
    game, database
):
    game, preparation = build_prepared_game(game, database)
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
    readiness = preparation.routes.readiness
    await readiness.prepare(origin, destination)
    approach = require_value(
        await readiness.prepare(owned[0].facility_uid, origin)
    )
    with database.connect() as conn:
        conn.execute(
            "DELETE FROM route_cache WHERE cache_key IN "
            "(SELECT cache_key FROM routing_relations WHERE relation_id=?)",
            (approach.reference.relation_id,),
        )
    assert readiness.ready(origin, destination) is not None
    publication = preparation.routes.ready_candidates((candidate,))
    assert len(publication) == 1
    assert publication[0].trade == candidate.trade
    with pytest.raises(ValueError, match="vorbereitet"):
        readiness.load(owned[0].facility_uid, origin)


@pytest.mark.asyncio
async def test_global_negative_cache_timeout_and_stale_payload(game, database):
    game, preparation = build_prepared_game(game, database)
    readiness = preparation.routes.readiness
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
    assert readiness.ready(*pair) == ready.reference
    assert readiness.store.payload(ready.reference) is None
    with pytest.raises(ValueError, match="vorbereitet"):
        readiness.load(*pair)
    readiness.timeout = 0.001

    async def slow_route(*args):
        await asyncio.sleep(1)

    readiness.router = AsyncMock()
    readiness.router.route.side_effect = slow_route
    readiness.provider_identity = "timeout-provider"
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
    game, preparation = build_prepared_game(game, database)
    readiness = preparation.routes.readiness
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
    assert readiness.router.route.await_count == 2


@pytest.mark.asyncio
async def test_worker_fills_ready_market_and_owns_shutdown(game, database):
    game, preparation = build_prepared_game(game, database)
    batch = make_stock_batch(game, preparation)
    preparation.demand.ensure()
    worker = MarketPreparationWorker(
        preparation.demand.jobs, lambda user: batch, game.now
    )
    assert preparation.demand.jobs.next_player(game.now()) == "test-owner"
    for _ in range(100):
        await worker.process("test-owner")
        if (
            require_value(preparation.demand.jobs.status("test-owner")).status
            == "ready"
        ):
            break
    assert (
        require_value(preparation.demand.jobs.status("test-owner")).status
        == "ready"
    )
    assert game.list_contracts()
    assert all(
        o.eligible_vehicle_ids
        for o in game.contract_choices(game.list_contracts())
    )
    await worker.start()
    worker.wake()
    assert worker._wake.is_set()
    foreign_loop = Mock()
    worker._loop = foreign_loop
    with patch(
        "app.services.preparation_worker.asyncio.get_running_loop",
        side_effect=RuntimeError,
    ):
        worker.wake()
    foreign_loop.call_soon_threadsafe.assert_called_once_with(worker._wake.set)
    worker._loop = asyncio.get_running_loop()
    with pytest.raises(RuntimeError):
        await worker.start()
    await asyncio.sleep(1.05)
    await worker.close()
    await worker.close()


@pytest.mark.asyncio
async def test_worker_idle_wait_finishes_on_safety_timeout(game, database):
    game, preparation = build_prepared_game(game, database)
    worker = MarketPreparationWorker(
        preparation.demand.jobs,
        lambda _user_id: make_stock_batch(game, preparation),
        game.now,
        PreparationWorkerTiming(idle_wait_seconds=0.001),
    )

    await worker._wait_for_work()

    assert not worker._wake.is_set()


def test_preparation_store_generation_and_reference_rollback(game, database):
    game, preparation = build_prepared_game(game, database)
    assert preparation.demand.jobs.status("missing") is None
    with pytest.raises(ValueError, match="publication"):
        preparation.routes.bind(game.state_repository.list_offers())
    preparation.demand.ensure()
    first = require_value(preparation.demand.jobs.status("test-owner"))
    assert game.preparation_status() == first
    preparation.demand.jobs.finish(
        "test-owner", "obsolete", "ready", None, game.now()
    )
    assert preparation.demand.jobs.status("test-owner") == first
    preparation.demand.jobs.finish(
        "test-owner", first.generation, "ready", None, game.now()
    )
    assert preparation.demand.jobs.next_player(game.now()) is None
    preparation.demand.jobs.request("test-owner", "new-generation", game.now())
    assert (
        require_value(preparation.demand.jobs.status("test-owner")).status
        == "partial"
    )


def test_preparation_composition_uses_complete_local_runtime(
    game,
    runtime,
):
    from app.bootstrap import (
        build_player_market_services,
        build_preparation_worker,
    )

    bound = build_player_market_services(runtime, "test-owner")
    assert bound.demand.user_id == "test-owner"
    worker = build_preparation_worker(runtime)
    from app.services.stock_preparation import StockPreparationBatch

    batch = worker.batches("test-owner")
    assert isinstance(batch, StockPreparationBatch)
    assert batch.publication.player_demand.user_id == "test-owner"


@pytest.mark.asyncio
async def test_preparation_failures_backoff_fencing_and_worker_cleanup(
    game,
    database,
):
    game, preparation = build_prepared_game(game, database)
    readiness = preparation.routes.readiness
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
    readiness.anchors = AsyncMock()
    readiness.anchors.max_snap_distance_m = 1000.0
    readiness.anchors.resolve.side_effect = RoutingError("locate unavailable")
    transient = require_value(await readiness.prepare(*pair))
    assert transient.status == "transient_failure"
    complete, retry = await preparation.route_preparation.prepare((candidate,))
    assert not complete and retry is not None
    readiness.provider_identity = "retry-generation"
    readiness.anchors = FakeRoutingAnchorResolver()
    with (
        patch.object(
            readiness.store, "publish_connection", return_value=False
        ),
        patch.object(readiness.store, "publish", return_value=False),
    ):
        assert await readiness.prepare(*pair) is None
        error = RoutingError("endpoint")
        error.category = "endpoint_unreachable"
        readiness.router = AsyncMock()
        readiness.router.route.side_effect = error
        assert await readiness.prepare(*pair) is None
        assert readiness.router.route.await_count == 1
    with patch.object(readiness, "prepare", return_value=None):
        complete, retry = await preparation.route_preparation.prepare(
            (candidate,)
        )
        assert not complete and retry is not None
    readiness.router = FakeRouter()
    with patch.object(readiness.store, "renew", return_value=False):
        assert await readiness.prepare(*pair) is None
    batch = make_stock_batch(game, preparation)
    preparation.demand.ensure()
    worker = MarketPreparationWorker(
        preparation.demand.jobs, lambda user: batch, game.now
    )
    with patch.object(worker, "process", side_effect=RuntimeError("batch")):
        await worker.start()
        await asyncio.sleep(0.01)
        await worker.close()
    assert (
        require_value(
            preparation.demand.jobs.status("test-owner")
        ).next_retry_at
        is not None
    )
    failed_worker = MarketPreparationWorker(
        preparation.demand.jobs, lambda user: batch, game.now
    )
    with patch.object(
        preparation.demand.jobs,
        "next_player",
        side_effect=RuntimeError("startup"),
    ):
        await failed_worker.start()
        assert failed_worker._task is not None
        assert not failed_worker._task.done()
        await failed_worker.close()


@pytest.mark.asyncio
async def test_route_publication_rechecks_inputs_after_provider_await(
    game, database
):
    game, preparation = build_prepared_game(game, database)
    readiness = preparation.routes.readiness
    offer = game.state_repository.list_offers()[0]
    pair = offer.origin.facility_uid, offer.destination.facility_uid
    original = readiness.world.read()
    changed = replace(original, facilities=original.facilities[:-1])
    with patch.object(
        readiness.world,
        "read",
        side_effect=[original, original, changed, changed],
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

    game, preparation = build_prepared_game(game, database)
    readiness = preparation.routes.readiness
    store = SqliteRoutingReadinessStore(database)
    readiness.provider_identity = "test"
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
async def test_dispatch_rejects_retired_and_changed_prepared_routes(
    game, database
):
    game, preparation = build_prepared_game(game, database)
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
    await preparation.routes.readiness.prepare(origin, destination)
    await preparation.routes.readiness.prepare(owned[0].facility_uid, origin)
    batch = make_stock_batch(game, preparation)
    preparation.demand.ensure()
    for _ in range(30):
        await batch.process()
        if game.list_contracts():
            break
    offer = game.list_contracts()[0]
    vehicle = owned[0]
    assert vehicle.location is not None
    planner = game.transport_dispatch.planning
    route = await planner.route(vehicle.location, offer)
    with (
        patch.object(
            type(preparation.routes),
            "matches_snapshot",
            return_value=False,
        ),
        patch.object(
            type(preparation.routes),
            "retained_current",
            return_value=False,
        ),
    ):
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
    with pytest.raises(ValueError, match="NHM-Tarif"):
        planner.quote(
            replace(offer, market_model="nhm_v1", market_context=None),
            route,
            vehicle,
            1,
        )
