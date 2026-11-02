"""Fenced, snapshot-consistent and atomic stock publication."""

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.errors import PersistenceError


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
    routing = prep.route_preparation.preparation
    original = routing.prepare

    async def change_vehicle(_service, *args):
        result = await original(*args)
        vehicle = game.get_vehicle("truck")
        vehicle.start_trip()
        game.state_repository.save_vehicle(vehicle)
        return result

    with patch.object(type(routing), "prepare", change_vehicle):
        assert (await batch.process()).status == "partial"
    assert game.state_repository.list_offers() == ()


def test_stock_publication_read_phases_preserve_one_snapshot(stock_game):
    """Keep authoritative reads, demand and readiness in explicit phases."""
    _, prep, batch = stock_game
    reader = batch.snapshots
    now = prep.demand.clock()
    inputs = reader.read_inputs()
    projection = reader.resolve_demand(inputs, now)
    assert prep.stores is not None
    templates = prep.stores.templates.scoped_templates(
        projection.template_scopes
    )
    candidates = reader.generation.candidates.build(
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
        prep.route_preparation.preparation.router,
        "route",
        new=AsyncMock(side_effect=error),
    ):
        for pair in required_relations(snapshot.candidates):
            await prep.route_preparation.preparation.prepare(*pair)
        assert (await batch.process()).status == "exhausted"
    assert game.state_repository.list_offers() == ()
    assert (
        prep.stores.templates.templates(
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
    arrivals = prep.stores.offers.arrivals()
    assert arrivals[0].transport_id == trip.id
    vehicle = game.get_vehicle("truck")
    vehicle.arrive(trip.destination)
    with pytest.raises(ValueError, match="enroute"):
        batch.snapshots.demand.resolve((vehicle,), arrivals, now)
    with database.connect() as db:
        db.execute("UPDATE transports SET destination_facility_uid='wrong'")
    with pytest.raises(PersistenceError, match="Ankunft"):
        prep.stores.offers.arrivals()


@pytest.mark.asyncio
async def test_reserve_replacement_and_publication_failure_keep_atomic_state(
    stock_game, database
):
    from app.services.gameplay.fleet import build_owned_vehicle

    game, prep, batch = stock_game
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    first = game.contract_choices(game.list_contracts(), "truck")[0].offer
    # The fixture's single model is exposed through the market catalogue.
    model = (
        game.market_lifecycle.generation.candidates.catalogue.list_models()[0]
    )
    second = build_owned_vehicle(
        model, "second", game.get_vehicle("truck").location
    )
    game.state_repository.save_vehicle(second)
    before = game.contract_choices(game.list_contracts(), "second")
    with (
        patch.object(
            type(prep.route_preparation.preparation),
            "prepare",
            new=AsyncMock(
                side_effect=AssertionError("Runtime calls provider")
            ),
        ),
        patch.object(
            game.market_lifecycle.generation.candidates,
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
    templates = prep.stores.templates.templates(
        (second.location.city.city_uid,)
    )
    assert len(templates) > 30
    assert (
        len(
            [
                t
                for t in templates
                if t.template_id not in prep.stores.offers.used()
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
    unused = prep.stores.offers.used()
    with patch.object(
        game.state_repository,
        "remove_offer",
        side_effect=RuntimeError("rollback"),
    ):
        with pytest.raises(RuntimeError, match="rollback"):
            await game.dispatch(next_offer.id, "second")
    assert prep.stores.offers.used() == unused
    assert game.get_vehicle("second").status == "idle"
