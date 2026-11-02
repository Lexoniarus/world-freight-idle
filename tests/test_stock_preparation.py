"""Incremental stock preparation and reusable supply integration."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_services import PlayerMarketServices
from app.services.market.player_stock import PlayerMarketStockContext
from app.services.market.route_preparation import (
    MarketRoutePreparationService,
)
from app.services.market.stock.preparation import StockPreparationBatch
from app.services.market.stock.publication import StockPublicationService
from app.services.market.stock.snapshot import StockSnapshotReader
from tests.support.game_clock import set_game_clock


@pytest.mark.asyncio
async def test_shared_stock_has_three_visible_ten_ready_and_does_not_expire(
    stock_game,
):
    game, prep, batch = stock_game
    build = game.market.candidates.build

    def outside_writer(*args):
        assert prep.stock.stock.database._active.get() is None
        return build(*args)

    with patch.object(
        game.market.candidates, "build", side_effect=outside_writer
    ):
        result = await batch.process()
    for _ in range(100):
        result = await batch.process()
        if result.status == "ready":
            break
    assert result.status == "ready"
    offers = game.list_contracts()
    assert len(offers) == 30
    choices = game.contract_choices(offers, "truck")
    assert len(choices) == 9
    assert all(
        sum(c.offer.market_context.distance_band == band for c in choices) == 3
        for band in ("short", "medium", "long")
    )
    assert all(o.expires_at is None for o in offers)
    assert (
        len(prep.stock.templates.templates((offers[0].origin.city.city_uid,)))
        == 30
    )
    assert game.refresh_contracts() == offers
    assert game.list_contracts() == offers
    ids = [o.id for o in offers]
    future = game.now() + 7 * 3600
    set_game_clock(game, lambda: future, batch.route_preparation)
    assert [o.id for o in game.list_contracts()] == ids
    chosen = choices[0].offer
    before = set(prep.stock.stock.bindings())
    await game.dispatch(chosen.id, "truck")
    assert len(prep.stock.stock.used()) == 1
    assert prep.stock.stock.used() <= before
    assert len(game.state_repository.list_offers()) == 29
    # Departure hides availability but does not delete the reserve.
    assert game.list_contracts() == []
    await batch.process()
    assert len(game.state_repository.list_offers()) == 29
    status = prep.demand.jobs.status(prep.demand.user_id)
    prep.demand.jobs.finish(
        prep.demand.user_id,
        status.generation,
        "ready",
        game.now() + 60,
        game.now(),
    )
    ready_status = prep.demand.jobs.status(prep.demand.user_id)
    assert game.list_contracts() == []
    assert prep.demand.jobs.status(prep.demand.user_id) == ready_status


@pytest.mark.asyncio
async def test_templates_are_shared_but_consumption_is_once_per_account(
    stock_game, database
):
    from app.domain.game import PlayerState
    from app.repositories.game_state import SqliteGameUnitOfWork
    from app.repositories.routing_readiness import SqliteOfferRouteStore

    game, prep, batch = stock_game
    for _ in range(100):
        if (await batch.process()).status == "ready":
            break
    templates = prep.stock.templates.templates(
        (game.get_vehicle("truck").location.city.city_uid,)
    )
    with database.transaction(), database.connect() as db:
        db.execute("INSERT INTO users VALUES ('other', 'Other', 'test', 0)")
        unit = SqliteGameUnitOfWork(database, "other")
        unit.repository.save_player(PlayerState(175000, 0, 0))
        unit.repository.save_vehicle(game.get_vehicle("truck"))
    other = PlayerMarketServices(
        PlayerMarketDemandService(
            "other",
            prep.demand.jobs,
            prep.demand.clock,
            database,
        ),
        PlayerMarketRouteService(
            prep.routes.readiness,
            SqliteOfferRouteStore(database, "other"),
            database,
        ),
        MarketRoutePreparationService(
            prep.routes.readiness,
            prep.route_preparation.preparation,
            prep.demand.clock,
        ),
        PlayerMarketStockContext(
            SqlitePlayerMarketStockStore(database, "other"),
            SqliteMarketTemplateStore(database),
        ),
    )
    other.demand.ensure()
    second = StockPreparationBatch(
        StockPublicationService(
            unit,
            game.market,
            other.demand,
            other.routes,
            other.stock,
            lambda: True,
        ),
        StockSnapshotReader(
            unit,
            game.market,
            other.demand,
            other.routes,
            other.stock,
            batch.snapshots.demand,
        ),
        batch.planning,
        batch.templates,
        other.route_preparation,
    )
    with patch.object(
        type(prep.route_preparation.preparation),
        "prepare",
        new=AsyncMock(
            side_effect=AssertionError("Cached roads must be reused")
        ),
    ):
        for _ in range(15):
            if (await second.process()).status == "ready":
                break
    assert (
        other.stock.templates.templates((templates[0].city_uid,)) == templates
    )
    common = next(
        iter(
            prep.stock.stock.bindings().keys()
            & other.stock.stock.bindings().keys()
        )
    )
    first_id, second_id = (
        prep.stock.stock.bindings()[common],
        other.stock.stock.bindings()[common],
    )
    assert first_id != second_id
    with database.transaction():
        prep.stock.stock.consume(first_id, game.now())
        with pytest.raises(ValueError, match="bereits verwendet"):
            prep.stock.stock.consume(first_id, game.now())
    assert common not in other.stock.stock.used()
    with database.transaction():
        other.stock.stock.consume(second_id, game.now())
    assert common in other.stock.stock.used()
    existing = next(
        o for o in game.state_repository.list_offers() if o.id == first_id
    )
    with pytest.raises(ValueError, match="bereits verwendet"):
        prep.stock.stock.issue(common, replace(existing, id="must-not-exist"))
    assert all(
        o.id != "must-not-exist" for o in game.state_repository.list_offers()
    )


@pytest.mark.asyncio
async def test_destination_stock_starts_at_dispatch_without_early_settlement(
    stock_game, database
):
    from unittest.mock import Mock

    from tests.transport_fixtures import add_transport

    game, prep, batch = stock_game
    now = game.now()
    trip = add_transport(game, departed_at=now, arrives_at=now + 7200)
    world = game.market.candidates.reference()
    output = world.facilities[0].nhm_profiles[0]
    updated = replace(
        world,
        facilities=tuple(
            replace(f, nhm_profiles=(*f.nhm_profiles, output))
            if f.facility_uid == trip.destination.facility_uid
            else f
            for f in world.facilities
        ),
    )
    reference = Mock(read=Mock(return_value=updated))
    game.market.candidates.world = reference
    prep.routes.readiness.world = reference
    clock = [trip.departed_at + 1]
    set_game_clock(game, lambda: clock[0], batch.route_preparation)
    prep.demand.clock = lambda: clock[0]
    batch.templates.clock = prep.demand.clock
    snapshot = batch.snapshots.read()
    arriving = next(d for d in snapshot.demands if d.transport_id)
    assert arriving.transport_id == trip.id
    assert arriving.vehicle.facility_uid == trip.destination.facility_uid
    assert game.get_vehicle("truck").facility_uid == trip.origin.facility_uid
    before = game.state_repository.get_player()
    for _ in range(35):
        if (await batch.process()).status == "ready":
            break
    prepared = game.state_repository.list_offers()
    assert prepared
    assert game.state_repository.get_player() == before
    assert game.get_vehicle("truck").status == "enroute"
    with pytest.raises(ValueError, match="einsatzbereites"):
        game.contract_choices(prepared, "truck")
    clock[0] = trip.arrives_at + 1
    assert game.reconcile_arrival()
    after = game.state_repository.get_player()
    assert not game.reconcile_arrival()
    assert game.state_repository.get_player() == after
    with patch.object(
        type(prep.route_preparation.preparation),
        "prepare",
        new=AsyncMock(side_effect=AssertionError("Runtime provider fallback")),
    ):
        choices = game.contract_choices(game.list_contracts(), "truck")
        assert choices
        assert set(c.offer.id for c in choices) <= {o.id for o in prepared}
        await game.dispatch(choices[0].offer.id, "truck")


@pytest.mark.asyncio
async def test_stale_evidence_reuses_offers_and_backoff_never_releases_stock(
    stock_game,
):
    game, prep, batch = stock_game
    now = [game.now()]
    set_game_clock(game, lambda: now[0], batch.route_preparation)
    prep.demand.clock = prep.routes.readiness.clock = lambda: now[0]
    batch.templates.clock = prep.demand.clock
    for _ in range(100):
        if (await batch.process()).status == "ready":
            break
    saved = game.state_repository.list_offers()
    now[0] += 7 * 24 * 3600
    assert game.list_contracts()
    assert game.state_repository.list_offers() == saved
    with patch.object(
        prep.route_preparation.preparation.router,
        "route",
        side_effect=AssertionError("Ready routes must remain reusable"),
    ):
        assert game.list_contracts()
        await batch.process()
    assert game.state_repository.list_offers() == saved


@pytest.mark.asyncio
async def test_partial_connection_resumes_after_restart_and_never_releases_early(
    stock_game,
):
    from app.domain.market_preparation import required_relations
    from app.services.market.vehicle_coverage import trade_key

    game, prep, batch = stock_game
    snapshot = batch.snapshots.read()
    target = next(
        t
        for t in batch.planning.targets(
            snapshot.demands, snapshot.candidates, snapshot.ready, ()
        )
    )
    remote = next(
        c
        for c in target.choices
        if c.trade.origin.facility_uid != target.demand.vehicle.facility_uid
    )
    with patch.object(type(batch), "_select", return_value=(target, remote)):
        await batch.process()
        assert game.state_repository.list_offers() == ()
        assert (
            sum(
                prep.routes.readiness.ready(*pair) is not None
                for pair in required_relations((remote,))
            )
            == 1
        )
        # Reopen the durable checkpoint and continue the other relation.
        prep.stock.stock = SqlitePlayerMarketStockStore(
            prep.stock.stock.database, prep.demand.user_id
        )
        assert prep.stock.stock.pending(target.key) == trade_key(remote)
        await batch.process()
    assert len(game.state_repository.list_offers()) == 1
    assert len(game.contract_choices(game.list_contracts(), "truck")) == 1


@pytest.mark.asyncio
async def test_catalogue_changes_block_old_supply_without_deleting_terms(
    stock_game,
):
    from unittest.mock import Mock

    from app.domain.market_profiles import TransportCapability

    game, prep, batch = stock_game
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    saved = game.state_repository.list_offers()
    with patch.object(
        game.market.candidates, "structurally_current", return_value=False
    ):
        snapshot = batch.snapshots.read()
        assert not snapshot.usable_offers
        assert not snapshot.usable_templates
        assert snapshot.offers == saved
        assert game.list_contracts() == []
    assert game.state_repository.list_offers() == saved
    # A changed freight class must not count incompatible old snapshots as
    # sufficient stock and thereby prevent the worker from replacing them.
    reference = game.market.candidates.reference()
    changed = replace(
        reference,
        market_profiles=tuple(
            replace(p, transport_class="special")
            for p in reference.market_profiles
        ),
    )
    game.market.candidates.world = Mock(read=Mock(return_value=changed))
    catalogue = game.market.candidates.catalogue
    models = tuple(
        replace(m, transport_capabilities=(TransportCapability("special", 1),))
        for m in catalogue.list_models()
    )
    with patch.object(catalogue, "list_models", return_value=models):
        assert game.list_contracts() == []
        snapshot = batch.snapshots.read()
        assert snapshot.ready and not snapshot.usable_offers
        assert not snapshot.usable_templates
        for _ in range(30):
            if (await batch.process()).status == "ready":
                break
        available = game.list_contracts()
        assert len(available) == 30
        assert all(
            o.market_context.transport_class == "special" for o in available
        )
    assert game.state_repository.list_offers()[: len(saved)] == saved


@pytest.mark.asyncio
async def test_parallel_dispatch_consumes_one_template_and_debits_once(
    stock_game,
):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.repositories.game_state import SqliteGameUnitOfWork
    from app.services.gameplay.dispatch import TransportDispatchService
    from app.services.gameplay.game import GameService
    from app.services.gameplay.initialization import (
        PlayerInitializationService,
    )
    from app.services.gameplay.settlement import TransportSettlementService
    from app.services.gameplay.vehicle_location import VehicleLocationResolver
    from app.services.market.lifecycle import MarketLifecycleService

    game, prep, batch = stock_game
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    offer = game.contract_choices(game.list_contracts(), "truck")[0].offer
    unit = SqliteGameUnitOfWork(
        prep.stock.stock.database,
        prep.demand.user_id,
    )
    lifecycle = MarketLifecycleService(
        unit,
        game.market,
        game.market_scope,
        game.now,
        prep.demand,
        prep.routes,
        prep.stock,
        selection=game.market_lifecycle.selection,
    )
    settlement = TransportSettlementService(
        unit,
        game.now,
        prep.demand,
    )
    dispatch_service = TransportDispatchService(
        unit,
        game.market,
        game.transport_dispatch.planning,
        game.transport_dispatch.eligibility,
        VehicleLocationResolver(game.world),
        settlement,
        game.now,
        game.time_scale,
        prep.demand,
        prep.stock,
    )
    other = GameService(
        unit,
        game.world,
        game.market,
        game.catalogue,
        game.market_scope,
        game.now,
        game.time_scale,
        lifecycle,
        PlayerInitializationService(
            unit,
            game.world,
            game.catalogue,
            prep.demand,
        ),
        settlement,
        dispatch_service,
        prep,
    )
    barrier = Barrier(2)
    original = TransportDispatchService.quote_contract

    async def together(service, contract_id, vehicle_id):
        quote = await original(service, contract_id, vehicle_id)
        barrier.wait(timeout=10)
        return quote

    def run_dispatch(service):
        try:
            return asyncio.run(service.dispatch(offer.id, "truck"))
        except (ValueError, KeyError) as error:
            return error

    before = game.state_repository.get_player().cash
    with (
        patch.object(TransportDispatchService, "quote_contract", new=together),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        futures = [
            pool.submit(run_dispatch, service) for service in (game, other)
        ]
        results = [f.result() for f in futures]
    assert sum(isinstance(r, (ValueError, KeyError)) for r in results) == 1
    trips = game.state_repository.list_active_transports()
    assert len(trips) == len(prep.stock.stock.used()) == 1
    assert game.state_repository.get_player().cash == (
        before - trips[0].operating_cost_eur
    )
