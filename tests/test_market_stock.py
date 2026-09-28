"""Reusable market supply, private consumption and fair preparation."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.domain.contracts import ContractOffer
from app.domain.errors import PersistenceError
from app.domain.market_stock import PreparedTemplate, StockPolicy
from app.domain.results import AvailableContract
from app.repositories.market_stock import SqliteMarketStockStore
from app.services.market_demand import MarketDemandResolver
from app.services.market_selection import MarketSelectionService
from app.services.market_templates import MarketTemplateService
from app.services.stock_planning import StockPlanningService
from app.services.stock_preparation import StockPreparationBatch
from app.services.stock_publication import StockPublicationService
from tests.test_market import city_market as city_market
from tests.test_vehicle_market import vehicle_game as vehicle_game


@pytest.fixture
def stock_game(vehicle_game, database):
    game, preparation = vehicle_game
    SqliteMarketStockStore.initialize(database)
    preparation.stock = SqliteMarketStockStore(database, "test-owner")
    game.market_lifecycle.selection = MarketSelectionService(
        preparation.policy
    )
    preparation.request()
    publication = StockPublicationService(
        game.unit_of_work,
        game.market,
        preparation,
        MarketDemandResolver(game.market.candidates),
        lambda: True,
    )
    batch = StockPreparationBatch(
        publication,
        StockPlanningService(preparation.policy),
        MarketTemplateService(
            game.market.factory, preparation.policy, preparation.clock
        ),
    )
    return game, preparation, batch


@pytest.mark.asyncio
async def test_shared_stock_has_three_visible_ten_ready_and_does_not_expire(
    stock_game,
):
    game, prep, batch = stock_game
    build = game.market.candidates.build

    def outside_writer(*args):
        assert prep.stock.database._active.get() is None
        return build(*args)

    with patch.object(
        game.market.candidates, "build", side_effect=outside_writer
    ):
        result = await batch.process()
    for _ in range(30):
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
    assert len(prep.stock.templates((offers[0].origin.city.city_uid,))) == 30
    assert game.refresh_contracts() == offers
    ids = [o.id for o in offers]
    with patch.object(game, "now", return_value=game.now() + 7 * 3600):
        assert [o.id for o in game.list_contracts()] == ids
    chosen = choices[0].offer
    before = set(prep.stock.bindings())
    await game.dispatch(chosen.id, "truck")
    assert len(prep.stock.used()) == 1
    assert prep.stock.used() <= before
    assert len(game.state_repository.list_offers()) == 29
    # Departure hides availability but does not delete the reserve.
    assert game.list_contracts() == []
    await batch.process()
    assert len(game.state_repository.list_offers()) == 29
    status = prep.jobs.status(prep.user_id)
    prep.jobs.finish(
        prep.user_id, status.generation, "ready", game.now() + 60, game.now()
    )
    ready_status = prep.jobs.status(prep.user_id)
    assert game.list_contracts() == []
    assert prep.jobs.status(prep.user_id) == ready_status


@pytest.mark.asyncio
async def test_templates_are_shared_but_consumption_is_once_per_account(
    stock_game, database
):
    from app.domain.game import PlayerState
    from app.repositories.game_state import SqliteGameUnitOfWork
    from app.repositories.routing_readiness import SqliteOfferRouteStore
    from app.services.market_preparation import MarketPreparationService

    game, prep, batch = stock_game
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    templates = prep.stock.templates(
        (game.get_vehicle("truck").location.city.city_uid,)
    )
    with database.transaction(), database.connect() as db:
        db.execute("INSERT INTO users VALUES ('other', 'Other', 'test', 0)")
        unit = SqliteGameUnitOfWork(database, "other")
        unit.repository.save_player(PlayerState(175000, 0, 0))
        unit.repository.save_vehicle(game.get_vehicle("truck"))
    other = MarketPreparationService(
        "other",
        prep.readiness,
        SqliteOfferRouteStore(database, "other"),
        prep.jobs,
        prep.clock,
        database,
        SqliteMarketStockStore(database, "other"),
    )
    other.request()
    assert other.stock is not None
    second = StockPreparationBatch(
        StockPublicationService(
            unit, game.market, other, batch.publication.demand, lambda: True
        ),
        batch.planning,
        batch.templates,
    )
    with patch.object(
        prep.readiness,
        "prepare",
        side_effect=AssertionError("Cached roads must be reused"),
    ):
        for _ in range(15):
            if (await second.process()).status == "ready":
                break
    assert other.stock.templates((templates[0].city_uid,)) == templates
    common = next(
        iter(prep.stock.bindings().keys() & other.stock.bindings().keys())
    )
    first_id, second_id = (
        prep.stock.bindings()[common],
        other.stock.bindings()[common],
    )
    assert first_id != second_id
    with database.transaction():
        prep.stock.consume(first_id, game.now())
        with pytest.raises(ValueError, match="bereits verwendet"):
            prep.stock.consume(first_id, game.now())
    assert common not in other.stock.used()
    with database.transaction():
        other.stock.consume(second_id, game.now())
    assert common in other.stock.used()
    existing = next(
        o for o in game.state_repository.list_offers() if o.id == first_id
    )
    with pytest.raises(ValueError, match="bereits verwendet"):
        prep.stock.issue(common, replace(existing, id="must-not-exist"))
    assert all(
        o.id != "must-not-exist" for o in game.state_repository.list_offers()
    )


@pytest.mark.asyncio
async def test_stock_fences_lease_loss_and_stale_routes_without_partial_issuance(
    stock_game,
):
    game, prep, batch = stock_game
    snapshot = batch.publication.read()
    batch.publication.guard = lambda: False
    assert (await batch.process()).status == "partial"
    assert game.state_repository.list_offers() == ()
    assert not batch.publication.publish(snapshot, (), ())
    batch.publication.guard = lambda: True
    original = prep.readiness.prepare

    async def change_vehicle(*args):
        result = await original(*args)
        vehicle = game.get_vehicle("truck")
        vehicle.start_trip()
        game.state_repository.save_vehicle(vehicle)
        return result

    with patch.object(prep.readiness, "prepare", side_effect=change_vehicle):
        assert (await batch.process()).status == "partial"
    assert game.state_repository.list_offers() == ()


def test_stock_policy_selection_and_corrupt_storage_are_rejected(
    stock_game, database
):
    game, prep, batch = stock_game
    for policy in ((0, 10, 3600), (4, 3, 3600), (3, 10, 0)):
        with pytest.raises(ValueError):
            StockPolicy(*policy)
    for invalid in (True, 3.5, float("inf")):
        with pytest.raises(ValueError):
            replace(StockPolicy(), reserve_per_band=invalid)
    snapshot = batch.publication.read()
    offer = ContractOffer.from_snapshot(
        game.market.factory.build(snapshot.candidates[0], 1)
    )
    template = PreparedTemplate(
        "template", "model", offer.origin.city.city_uid, offer
    )
    for invalid in (
        replace(offer, expires_at=2),
        replace(offer, market_model="old", market_context=None),
    ):
        with pytest.raises(ValueError):
            PreparedTemplate(
                "bad", "model", offer.origin.city.city_uid, invalid
            )
    with pytest.raises(ValueError):
        PreparedTemplate("bad", "model", "wrong", offer)
    prep.stock.add(template)
    with pytest.raises(PersistenceError):
        prep.stock.add(template)
    SqliteMarketStockStore.initialize(database)
    assert prep.stock.templates((template.city_uid,)) == (template,)
    assert prep.stock.templates(()) == ()
    assert prep.stock.cursor() == ""
    assert prep.stock.pending("context") is None
    prep.stock.checkpoint("context", ("a", "b", 1))
    assert prep.stock.cursor() == "context"
    assert prep.stock.pending("context") == ("a", "b", 1)
    prep.stock.checkpoint("context", None)
    assert prep.stock.pending("context") is None
    prep.stock.consume("unbound-legacy", 1)
    selected = MarketSelectionService(StockPolicy()).select(
        tuple(
            AvailableContract(replace(offer, id=str(i)), ("truck", "other"))
            for i in range(12)
        ),
        "truck",
    )
    assert len(selected) == 3
    assert all(o.eligible_vehicle_ids == ("truck",) for o in selected)
    assert (
        MarketSelectionService(StockPolicy()).select(
            (
                AvailableContract(
                    replace(offer, market_model="legacy", market_context=None),
                    ("truck",),
                ),
            ),
            None,
        )
        == ()
    )
    with database.connect() as db:
        db.execute("UPDATE market_templates SET model_id=''")
    with pytest.raises(PersistenceError):
        prep.stock.templates((template.city_uid,))


@pytest.mark.asyncio
async def test_arrival_stock_starts_at_horizon_without_early_settlement(
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
    prep.readiness.world = reference
    clock = [trip.arrives_at - 3601]
    game.now = prep.clock = lambda: clock[0]
    batch.templates.clock = prep.clock
    assert batch.publication.read().demands == ()
    assert (await batch.process()).status == "ready"
    clock[0] += 1
    snapshot = batch.publication.read()
    arriving = next(d for d in snapshot.demands if not d.catalogue_only)
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
        prep.readiness,
        "prepare",
        side_effect=AssertionError("Runtime provider fallback"),
    ):
        choices = game.contract_choices(game.list_contracts(), "truck")
        assert choices
        assert set(c.offer.id for c in choices) <= {o.id for o in prepared}
        await game.dispatch(choices[0].offer.id, "truck")


@pytest.mark.asyncio
async def test_stale_evidence_reuses_offers_and_backoff_never_releases_stock(
    stock_game,
):
    from app.domain.errors import RoutingError
    from app.domain.market_preparation import required_relations
    from app.domain.routing_anchors import POSITIVE_TTL

    game, prep, batch = stock_game
    now = [game.now()]
    game.now = prep.clock = prep.readiness.clock = lambda: now[0]
    batch.templates.clock = prep.clock
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    saved = game.state_repository.list_offers()
    now[0] += POSITIVE_TTL + 1
    assert game.list_contracts() == []
    assert game.state_repository.list_offers() == saved
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    assert game.state_repository.list_offers() == saved
    assert game.list_contracts()
    snapshot = batch.publication.read()
    pairs = required_relations(snapshot.candidates)
    from unittest.mock import AsyncMock

    error = RoutingError("unavailable")
    error.category = "provider_unavailable"
    now[0] += POSITIVE_TTL + 1
    with patch.object(
        prep.readiness.router, "route", new=AsyncMock(side_effect=error)
    ):
        for pair in pairs:
            await prep.readiness.prepare(*pair)
        result = await batch.process()
    assert result.status == "partial"
    assert result.retry_at > now[0]
    assert game.list_contracts() == []
    assert game.state_repository.list_offers() == saved


def test_stock_rotation_prioritizes_unserved_vehicles_and_resumes_work(
    stock_game,
):
    from app.domain.market_stock import MarketDemand
    from app.services.stock_planning import StockTarget
    from app.services.vehicle_coverage import trade_key

    game, prep, batch = stock_game
    snapshot = batch.publication.read()
    candidate = snapshot.candidates[0]
    demand = snapshot.demands[0]
    supplied = StockTarget(demand, "short", 1, 0, (candidate,), 7)
    missing = replace(
        supplied,
        demand=MarketDemand(replace(demand.vehicle, vehicle_id="z-truck"), 0),
        count=0,
        total_available=0,
    )
    assert batch.planning.order((supplied, missing), "")[0] == missing
    other = replace(missing, band="long")
    first, second = batch.planning.order((missing, other), "")
    assert batch.planning.order((missing, other), first.key)[0] == second
    assert batch.planning.choose(first, trade_key(candidate), ()) == candidate
    assert batch.planning.targets((), (), (), (), ()) == ()


@pytest.mark.asyncio
async def test_failed_approaches_and_changed_publication_do_not_create_ready_offers(
    stock_game,
):
    from unittest.mock import AsyncMock

    from app.domain.errors import RoutingError
    from app.domain.market_preparation import required_relations

    game, prep, batch = stock_game
    snapshot = batch.publication.read()
    error = RoutingError("no way")
    error.category = "no_path"
    with patch.object(
        prep.readiness.router, "route", new=AsyncMock(side_effect=error)
    ):
        for pair in required_relations(snapshot.candidates):
            await prep.readiness.prepare(*pair)
        assert (await batch.process()).status == "exhausted"
    assert game.state_repository.list_offers() == ()
    assert (
        prep.stock.templates(
            tuple({d.vehicle.city_uid for d in snapshot.demands})
        )
        == ()
    )
    with patch.object(
        type(batch.publication), "unchanged", return_value=False
    ):
        assert not batch.publication.publish(snapshot, (), ())


@pytest.mark.asyncio
async def test_arrival_projection_rejects_inconsistent_locations_and_idle_vehicle(
    stock_game, database
):
    from tests.transport_fixtures import add_transport

    game, prep, batch = stock_game
    now = game.now()
    trip = add_transport(game, departed_at=now, arrives_at=now + 60)
    arrivals = prep.stock.arrivals(now + 60)
    assert arrivals[0].transport_id == trip.id
    vehicle = game.get_vehicle("truck")
    vehicle.arrive(trip.destination)
    with pytest.raises(ValueError, match="enroute"):
        batch.publication.demand.resolve((vehicle,), arrivals, now)
    with database.connect() as db:
        db.execute("UPDATE transports SET destination_facility_uid='wrong'")
    with pytest.raises(PersistenceError, match="Ankunft"):
        prep.stock.arrivals(now + 60)


@pytest.mark.asyncio
async def test_reserve_replacement_and_publication_failure_keep_atomic_state(
    stock_game, database
):
    from app.services.fleet import build_owned_vehicle

    game, prep, batch = stock_game
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    first = game.contract_choices(game.list_contracts(), "truck")[0].offer
    # The fixture's single model is exposed through the market catalogue.
    model = game.market.candidates.catalogue.list_models()[0]
    second = build_owned_vehicle(
        model, "second", game.get_vehicle("truck").location
    )
    game.state_repository.save_vehicle(second)
    before = game.contract_choices(game.list_contracts(), "second")
    with (
        patch.object(
            prep.readiness,
            "prepare",
            side_effect=AssertionError("Runtime calls provider"),
        ),
        patch.object(
            game.market.candidates,
            "build",
            side_effect=AssertionError("Runtime builds candidates"),
        ),
    ):
        await game.dispatch(first.id, "truck")
        after = game.contract_choices(game.list_contracts(), "second")
    assert len(before) == len(after) == 9
    assert first.id not in {c.offer.id for c in after}
    assert {c.offer.id for c in after} - {c.offer.id for c in before}
    await batch.process()
    for _ in range(15):
        if (await batch.process()).status == "ready":
            break
    assert len(game.state_repository.list_offers()) >= 30
    assert second.location is not None
    templates = prep.stock.templates((second.location.city.city_uid,))
    assert len(templates) > 30
    assert (
        len([t for t in templates if t.template_id not in prep.stock.used()])
        >= 30
    )
    snapshot = batch.publication.read()
    original_ready = prep.readiness.ready
    reads = 0

    def changed(origin, destination):
        nonlocal reads
        reads += 1
        return (
            original_ready(origin, destination)
            if reads <= len(snapshot.offers)
            else None
        )

    with patch.object(prep.readiness, "ready", side_effect=changed):
        assert not batch.publication.publish(snapshot, (), ())
    assert game.state_repository.list_offers() == snapshot.offers
    # A failed financial transaction cannot retain a consumption record.
    next_offer = after[0].offer
    unused = prep.stock.used()
    with patch.object(
        game.state_repository,
        "remove_offer",
        side_effect=RuntimeError("rollback"),
    ):
        with pytest.raises(RuntimeError, match="rollback"):
            await game.dispatch(next_offer.id, "second")
    assert prep.stock.used() == unused
    assert game.get_vehicle("second").status == "idle"


def test_demand_models_and_owned_capacity_remain_separate(stock_game):
    from app.domain.market_compatibility import planning_vehicle

    game, prep, batch = stock_game
    vehicle = game.get_vehicle("truck")
    catalogue = game.market.candidates.catalogue
    model = catalogue.list_models()[0]
    with pytest.raises(ValueError, match="Fahrzeugmodell"):
        planning_vehicle(
            vehicle, replace(model, id="different"), vehicle.location
        )
    models = (
        model,
        replace(model, id="second-model", capacity_tons=1),
        replace(model, id="train", mode="rail"),
    )
    with patch.object(catalogue, "list_models", return_value=models):
        demands = batch.publication.demand.resolve((vehicle,), (), 1)
    assert {d.vehicle.model_id for d in demands} == {model.id, "second-model"}
    assert any(d.catalogue_only for d in demands)
    assert (
        next(d for d in demands if not d.catalogue_only).vehicle.capacity_tons
        == vehicle.capacity_tons
    )


@pytest.mark.asyncio
async def test_partial_connection_resumes_after_restart_and_never_releases_early(
    stock_game,
):
    from app.domain.market_preparation import required_relations
    from app.services.vehicle_coverage import trade_key

    game, prep, batch = stock_game
    snapshot = batch.publication.read()
    target = next(
        t
        for t in batch.planning.targets(
            snapshot.demands, snapshot.candidates, snapshot.ready, (), ()
        )
        if not t.demand.catalogue_only
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
                prep.readiness.ready(*pair) is not None
                for pair in required_relations((remote,))
            )
            == 1
        )
        # Reopen the durable checkpoint and continue the other relation.
        prep.stock = SqliteMarketStockStore(prep.stock.database, prep.user_id)
        assert prep.stock.pending(target.key) == trade_key(remote)
        await batch.process()
    assert len(game.state_repository.list_offers()) == 3
    assert len(game.contract_choices(game.list_contracts(), "truck")) == 3


@pytest.mark.asyncio
async def test_all_catalogue_models_get_reserves_without_overloading_small_truck(
    stock_game,
):
    from app.services.fleet import build_owned_vehicle

    game, prep, batch = stock_game
    catalogue = game.market.candidates.catalogue
    model = catalogue.list_models()[0]
    models = (model,) + tuple(
        replace(model, id=f"model-{i}", capacity_tons=float(i + 1))
        for i in range(13)
    )
    vehicle = build_owned_vehicle(
        replace(model, capacity_tons=1.0),
        "truck",
        game.get_vehicle("truck").location,
    )
    game.state_repository.save_vehicle(vehicle)
    with patch.object(catalogue, "list_models", return_value=models):
        for _ in range(90):
            if (await batch.process()).status == "ready":
                break
        snapshot = batch.publication.read()
        for model in models:
            for band in ("short", "medium", "long"):
                templates = tuple(
                    t
                    for t in snapshot.templates
                    if t.model_id == model.id
                    and t.offer.market_context.distance_band == band
                )
                assert len(templates) >= 10
                assert all(
                    t.offer.tons <= model.capacity_tons for t in templates
                )
        choices = game.contract_choices(game.list_contracts(), "truck")
    assert len(choices) == 9
    assert all(c.offer.tons <= 1 for c in choices)


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
        snapshot = batch.publication.read()
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
        snapshot = batch.publication.read()
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
    from app.services.game import GameService

    game, prep, batch = stock_game
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    offer = game.contract_choices(game.list_contracts(), "truck")[0].offer
    other = GameService(
        SqliteGameUnitOfWork(prep.stock.database, prep.user_id),
        game.world,
        game.router,
        game.market,
        game.catalogue,
        game.market_scope,
        game.now,
        game.dispatch_planning,
        preparation=prep,
    )
    barrier = Barrier(2)
    original = GameService.quote_contract

    async def together(service, contract_id, vehicle_id):
        quote = await original(service, contract_id, vehicle_id)
        barrier.wait(timeout=10)
        return quote

    def dispatch(service):
        try:
            return asyncio.run(service.dispatch(offer.id, "truck"))
        except (ValueError, KeyError) as error:
            return error

    before = game.state_repository.get_player().cash
    with (
        patch.object(GameService, "quote_contract", new=together),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        futures = [pool.submit(dispatch, service) for service in (game, other)]
        results = [f.result() for f in futures]
    assert sum(isinstance(r, (ValueError, KeyError)) for r in results) == 1
    trips = game.state_repository.list_active_transports()
    assert len(trips) == len(prep.stock.used()) == 1
    assert game.state_repository.get_player().cash == (
        before - trips[0].operating_cost_eur
    )
