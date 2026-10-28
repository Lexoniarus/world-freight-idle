"""Reusable market supply, private consumption and fair preparation."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.domain.contracts import ContractOffer
from app.domain.errors import PersistenceError
from app.domain.market_stock import PreparedTemplate, StockPolicy
from app.domain.results import AvailableContract
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.services.deterministic_market_random import DeterministicMarketRandom
from app.services.market_demand import MarketDemandResolver
from app.services.market_selection import MarketSelectionService
from app.services.market_templates import MarketTemplateService
from app.services.player_market_demand import PlayerMarketDemandService
from app.services.player_market_routes import PlayerMarketRouteService
from app.services.player_market_services import PlayerMarketServices
from app.services.player_market_stock import PlayerMarketStockContext
from app.services.stock_planning import StockPlanningService
from app.services.stock_preparation import StockPreparationBatch
from app.services.stock_publication import StockPublicationService
from app.services.stock_snapshot import StockSnapshotReader
from tests.test_market import city_market as city_market
from tests.test_vehicle_market import vehicle_game as vehicle_game


@pytest.fixture
def stock_game(vehicle_game, database):
    game, preparation = vehicle_game
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    game.market_lifecycle.selection = MarketSelectionService(
        preparation.stock.policy
    )
    preparation.demand.request()
    demand = MarketDemandResolver(game.market.candidates)
    publication = StockPublicationService(
        game.unit_of_work,
        game.market,
        preparation.demand,
        preparation.routes,
        preparation.stock,
        lambda: True,
    )
    batch = StockPreparationBatch(
        publication,
        StockSnapshotReader(
            game.unit_of_work,
            game.market,
            preparation.demand,
            preparation.routes,
            preparation.stock,
            demand,
        ),
        StockPlanningService(preparation.stock.policy),
        MarketTemplateService(
            game.market.factory,
            preparation.stock.policy,
            preparation.demand.clock,
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
    with patch.object(game, "now", return_value=game.now() + 7 * 3600):
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
            prep.demand.clock,
            database,
        ),
        PlayerMarketStockContext(
            SqlitePlayerMarketStockStore(database, "other"),
            SqliteMarketTemplateStore(database),
        ),
    )
    other.demand.request()
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
    )
    with patch.object(
        prep.routes.readiness,
        "prepare",
        side_effect=AssertionError("Cached roads must be reused"),
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
async def test_stock_fences_lease_loss_and_stale_routes_without_partial_issuance(
    stock_game,
):
    game, prep, batch = stock_game
    snapshot = batch.snapshots.read()
    batch.publication.guard = lambda: False
    assert (await batch.process()).status == "partial"
    assert game.state_repository.list_offers() == ()
    assert not batch.publication.publish(snapshot, (), ())
    batch.publication.guard = lambda: True
    original = prep.routes.readiness.prepare

    async def change_vehicle(*args):
        result = await original(*args)
        vehicle = game.get_vehicle("truck")
        vehicle.start_trip()
        game.state_repository.save_vehicle(vehicle)
        return result

    with patch.object(
        prep.routes.readiness, "prepare", side_effect=change_vehicle
    ):
        assert (await batch.process()).status == "partial"
    assert game.state_repository.list_offers() == ()


def test_stock_publication_read_phases_preserve_one_snapshot(stock_game):
    """Keep authoritative reads, demand and readiness in explicit phases."""
    _, prep, batch = stock_game
    reader = batch.snapshots
    now = prep.demand.clock()
    inputs = reader.read_inputs()
    projection = reader.resolve_demand(inputs, now)
    assert prep.stock is not None
    templates = prep.stock.templates.scoped_templates(
        projection.template_scopes
    )
    candidates = reader.market.candidates.build(
        projection.cities,
        tuple(demand.vehicle for demand in projection.demands),
    )
    ready, evidence = reader.read_readiness(candidates)
    snapshot = reader.assemble(
        inputs,
        projection,
        candidates,
        ready,
        templates,
        evidence,
        now,
    )
    assert snapshot.owned == inputs.owned
    assert snapshot.demands == projection.demands
    assert snapshot.candidates == candidates
    assert snapshot.ready == ready
    assert snapshot.evidence == evidence
    assert snapshot.template_scopes == projection.template_scopes


def test_structural_candidates_are_reused_until_fleet_context_changes(
    stock_game,
):
    """Reuse expensive trade projections without freezing changed demand."""
    game, _, batch = stock_game
    candidates = game.market.candidates
    snapshot = batch.snapshots.read()
    cities = tuple(sorted({d.vehicle.city_uid for d in snapshot.demands}))
    fleet = tuple(d.vehicle for d in snapshot.demands)
    first = candidates.build(cities, fleet)
    assert candidates.build(cities, fleet) is first
    changed = replace(fleet[0], capacity_tons=fleet[0].capacity_tons + 1)
    rebuilt = candidates.build(cities, (changed, *fleet[1:]))
    assert rebuilt is not first


def test_stock_publication_plan_contains_coverage_and_routes(stock_game):
    """Calculate coverage and route bindings before the writer opens."""
    _, _, batch = stock_game
    publication = batch.publication
    snapshot = batch.snapshots.read()
    plan = publication._build_publication_plan(snapshot, ())
    assert plan.offers == snapshot.offers
    assert len(plan.coverage) == len(
        [demand for demand in snapshot.demands if not demand.transport_id]
    )
    assert {offer_id for offer_id, _ in plan.bindings} <= {
        offer.id for offer in plan.offers
    }


def test_stock_publication_commit_is_fenced_and_atomic(stock_game):
    """Reject stale plans and commit unchanged plans as one unit."""
    _, _, batch = stock_game
    publication = batch.publication
    snapshot = batch.snapshots.read()
    plan = publication._build_publication_plan(snapshot, ())
    original_guard = publication.guard
    publication.guard = lambda: False
    assert not publication._commit_publication(snapshot, (), (), plan)
    publication.guard = original_guard
    assert publication._commit_publication(snapshot, (), (), plan)


def test_stock_policy_selection_and_corrupt_storage_are_rejected(
    stock_game, database
):
    game, prep, batch = stock_game
    for policy in ((0, 10), (4, 3)):
        with pytest.raises(ValueError):
            StockPolicy(*policy)
    for invalid in (True, 3.5, float("inf")):
        with pytest.raises(ValueError):
            replace(StockPolicy(), reserve_per_band=invalid)
    snapshot = batch.snapshots.read()
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
    prep.stock.templates.add(template)
    with pytest.raises(PersistenceError):
        prep.stock.templates.add(template)
    SqlitePlayerMarketStockStore.initialize(database)
    assert prep.stock.templates.templates((template.city_uid,)) == (template,)
    assert prep.stock.templates.scoped_templates(
        ((template.city_uid, template.model_id),)
    ) == (template,)
    assert prep.stock.templates.scoped_templates(()) == ()
    assert (
        prep.stock.templates.scoped_templates(((template.city_uid, "other"),))
        == ()
    )
    assert prep.stock.templates.templates(()) == ()
    assert prep.stock.stock.cursor() == ""
    assert prep.stock.stock.pending("context") is None
    prep.stock.stock.checkpoint("context", ("a", "b", 1))
    assert prep.stock.stock.cursor() == "context"
    assert prep.stock.stock.pending("context") == ("a", "b", 1)
    prep.stock.stock.checkpoint("context", None)
    assert prep.stock.stock.pending("context") is None
    prep.stock.stock.consume("unbound-legacy", 1)
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
        prep.stock.templates.templates((template.city_uid,))
    with pytest.raises(PersistenceError):
        prep.stock.templates.scoped_templates(((template.city_uid, ""),))


def test_complete_stock_target_does_not_materialize_another_offer(stock_game):
    """Keep a satisfied band from creating redundant templates."""
    _, _, batch = stock_game
    snapshot = batch.snapshots.read()
    target = batch.planning.targets(
        snapshot.demands,
        snapshot.candidates,
        snapshot.ready,
        snapshot.usable_offers,
    )[0]
    limit = (
        batch.templates.policy.visible_per_band
        if target.priority < 2
        else batch.templates.policy.reserve_per_band
    )
    assert batch.templates.materialize(
        (),
        frozenset(),
        {},
        replace(target, count=limit),
        target.choices[0],
    ) == ((), ())


@pytest.mark.asyncio
async def test_refill_rechecks_target_after_preparing_a_route(stock_game):
    """Fence publication when another writer satisfies the selected band."""
    _, _, batch = stock_game
    snapshot = batch.snapshots.read()
    targets = batch.planning.targets(
        snapshot.demands,
        snapshot.candidates,
        snapshot.ready,
        snapshot.usable_offers,
    )
    with patch.object(
        type(batch.planning), "targets", side_effect=(targets, ())
    ):
        result = await batch.process()
    assert result.status == "partial"


def test_deterministic_market_random_is_stable_and_rejects_bad_choices(
    stock_game,
):
    """Keep market terms reproducible without reusing offer identities."""
    game, _, batch = stock_game
    candidate = batch.snapshots.read().candidates[0]
    first = game.market.factory.build(candidate, 10, "stable-context")
    second = game.market.factory.build(candidate, 10, "stable-context")
    assert first.id != second.id
    assert replace(second, id=first.id) == first
    random = DeterministicMarketRandom()
    selected = random.weighted_index(("a", "b"), (1.0, 2.0), "context")
    reversed_selected = random.weighted_index(
        ("b", "a"), (2.0, 1.0), "context"
    )
    assert ("a", "b")[selected] == ("b", "a")[reversed_selected]
    assert 0 < random.fraction("context") < 1
    for identities, weights in (
        ((), ()),
        (("a",), ()),
        (("a", "a"), (1.0, 1.0)),
        (("a",), (0.0,)),
    ):
        with pytest.raises(ValueError):
            random.weighted_index(identities, weights, "context")


def test_contract_factory_draw_is_context_stable_with_fresh_identity(
    stock_game,
):
    """Keep vehicle and load draws stable while identities remain unique."""
    game, _, batch = stock_game
    candidate = batch.snapshots.read().candidates[0]
    factory = game.market.factory
    first = factory._draw_offer(candidate, "stable-draw")
    second = factory._draw_offer(
        replace(candidate, vehicles=tuple(reversed(candidate.vehicles))),
        "stable-draw",
    )
    assert first.vehicle == second.vehicle
    assert first.load_factor == second.load_factor
    assert first.offer_id != second.offer_id


def test_contract_factory_derives_terms_from_selected_vehicle(stock_game):
    """Bind quantity and economics to the selected vehicle facts."""
    game, _, batch = stock_game
    candidate = batch.snapshots.read().candidates[0]
    draw = game.market.factory._draw_offer(candidate, "stable-terms")
    terms = game.market.factory._derive_terms(candidate, draw)
    assert 0 < terms.tons <= draw.vehicle.capacity_tons
    assert terms.context.generated_capacity_tons == draw.vehicle.capacity_tons
    assert (
        terms.context.distance_band == candidate.distance_profile.distance_band
    )
    assert terms.context.cargo_value_eur == round(
        terms.tons * candidate.profile.value_eur_per_t
    )


def test_contract_factory_snapshots_catalogue_evidence(stock_game):
    """Persist the chosen identity, terms and source evidence together."""
    game, _, batch = stock_game
    candidate = batch.snapshots.read().candidates[0]
    factory = game.market.factory
    draw = factory._draw_offer(candidate, "stable-snapshot")
    terms = factory._derive_terms(candidate, draw)
    snapshot = factory._build_snapshot(candidate, 123.0, draw, terms)
    assert snapshot.id == draw.offer_id
    assert snapshot.tons == terms.tons
    assert snapshot.market_context == terms.context
    assert snapshot.created_at == 123.0
    assert snapshot.origin_cargo_evidence == candidate.trade.origin_cargo
    assert snapshot.destination_cargo_evidence == (
        candidate.trade.destination_cargo
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
    game.now = prep.demand.clock = lambda: clock[0]
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
        prep.routes.readiness,
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
    game, prep, batch = stock_game
    now = [game.now()]
    game.now = prep.demand.clock = prep.routes.readiness.clock = lambda: now[0]
    batch.templates.clock = prep.demand.clock
    for _ in range(100):
        if (await batch.process()).status == "ready":
            break
    saved = game.state_repository.list_offers()
    now[0] += 7 * 24 * 3600
    assert game.list_contracts()
    assert game.state_repository.list_offers() == saved
    with patch.object(
        prep.routes.readiness.router,
        "route",
        side_effect=AssertionError("Ready routes must remain reusable"),
    ):
        assert game.list_contracts()
        await batch.process()
    assert game.state_repository.list_offers() == saved


def test_stock_rotation_prioritizes_unserved_vehicles_and_resumes_work(
    stock_game,
):
    from app.domain.market_stock import MarketDemand
    from app.services.stock_planning import StockTarget
    from app.services.vehicle_coverage import trade_key

    game, prep, batch = stock_game
    snapshot = batch.snapshots.read()
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
    assert batch.planning.targets((), (), (), ()) == ()


@pytest.mark.asyncio
async def test_failed_approaches_and_changed_publication_do_not_create_ready_offers(
    stock_game,
):
    from unittest.mock import AsyncMock

    from app.domain.errors import RoutingError
    from app.domain.market_preparation import required_relations

    game, prep, batch = stock_game
    snapshot = batch.snapshots.read()
    error = RoutingError("no way")
    error.category = "no_path"
    with patch.object(
        prep.routes.readiness.router, "route", new=AsyncMock(side_effect=error)
    ):
        for pair in required_relations(snapshot.candidates):
            await prep.routes.readiness.prepare(*pair)
        assert (await batch.process()).status == "exhausted"
    assert game.state_repository.list_offers() == ()
    assert (
        prep.stock.templates.templates(
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
    arrivals = prep.stock.stock.arrivals()
    assert arrivals[0].transport_id == trip.id
    vehicle = game.get_vehicle("truck")
    vehicle.arrive(trip.destination)
    with pytest.raises(ValueError, match="enroute"):
        batch.snapshots.demand.resolve((vehicle,), arrivals, now)
    with database.connect() as db:
        db.execute("UPDATE transports SET destination_facility_uid='wrong'")
    with pytest.raises(PersistenceError, match="Ankunft"):
        prep.stock.stock.arrivals()


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
            prep.routes.readiness,
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
    templates = prep.stock.templates.templates(
        (second.location.city.city_uid,)
    )
    assert len(templates) > 30
    assert (
        len(
            [
                t
                for t in templates
                if t.template_id not in prep.stock.stock.used()
            ]
        )
        >= 30
    )
    snapshot = batch.snapshots.read()
    original_ready = prep.routes.readiness.ready
    reads = 0

    def changed(origin, destination):
        nonlocal reads
        reads += 1
        return (
            original_ready(origin, destination)
            if reads <= len(snapshot.offers)
            else None
        )

    with patch.object(prep.routes.readiness, "ready", side_effect=changed):
        assert not batch.publication.publish(snapshot, (), ())
    assert game.state_repository.list_offers() == snapshot.offers
    # A failed financial transaction cannot retain a consumption record.
    next_offer = after[0].offer
    unused = prep.stock.stock.used()
    with patch.object(
        game.state_repository,
        "remove_offer",
        side_effect=RuntimeError("rollback"),
    ):
        with pytest.raises(RuntimeError, match="rollback"):
            await game.dispatch(next_offer.id, "second")
    assert prep.stock.stock.used() == unused
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
        demands = batch.snapshots.demand.resolve((vehicle,), (), 1)
    assert {d.vehicle.model_id for d in demands} == {model.id}
    assert demands[0].vehicle.capacity_tons == vehicle.capacity_tons


@pytest.mark.asyncio
async def test_partial_connection_resumes_after_restart_and_never_releases_early(
    stock_game,
):
    from app.domain.market_preparation import required_relations
    from app.services.vehicle_coverage import trade_key

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
    from app.services.game import GameService

    game, prep, batch = stock_game
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    offer = game.contract_choices(game.list_contracts(), "truck")[0].offer
    other = GameService(
        SqliteGameUnitOfWork(prep.stock.stock.database, prep.demand.user_id),
        game.world,
        game.router,
        game.market,
        game.catalogue,
        game.market_scope,
        game.now,
        game.dispatch_planning,
        game.dispatch_eligibility,
        market_services=prep,
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
    assert len(trips) == len(prep.stock.stock.used()) == 1
    assert game.state_repository.get_player().cash == (
        before - trips[0].operating_cost_eur
    )
