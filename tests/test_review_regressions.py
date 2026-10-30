"""Protect readiness recovery, atomic references and typed boundaries."""

import asyncio
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.bootstrap import build_economy_audit
from app.domain.errors import PersistenceError, RoutingError
from app.domain.market_preparation import PreparationStatus
from app.services.economy_audit import summarize_economy
from app.services.preparation_worker import MarketPreparationWorker
from tests.support.market import (
    build_prepared_game,
    make_stock_batch,
    require_value,
)


@pytest.mark.asyncio
async def test_exhausted_negative_demand_requires_explicit_invalidation(
    game, database
):
    game, preparation = build_prepared_game(game, database)
    fleet = game.market.candidates.resolve_fleet(
        game.state_repository.list_vehicles()
    )
    pool = game.market.candidates.build(
        game.market_scope.resolve(game.state_repository.list_vehicles()), fleet
    )
    candidate = pool[0]
    pair = (
        candidate.trade.origin.facility_uid,
        candidate.trade.destination.facility_uid,
    )
    readiness = preparation.routes.readiness
    routing = preparation.route_preparation.preparation
    error = RoutingError("No path")
    error.category = "no_path"
    routing.router = AsyncMock()
    routing.router.route.side_effect = error
    await routing.prepare(*pair)
    preparation.demand.ensure()
    status = require_value(preparation.demand.jobs.status("test-owner"))
    preparation.demand.jobs.finish(
        "test-owner", status.generation, "exhausted", None, game.now()
    )
    preparation.demand.ensure()
    assert preparation.demand.jobs.next_player(game.now()) is None
    before = preparation.routes.demand_state(*pair)
    readiness.provider_revision = lambda: "new-graph"
    after = preparation.routes.demand_state(*pair)
    assert after.expected_fingerprint != before.expected_fingerprint
    preparation.demand.invalidate()
    changed = require_value(preparation.demand.jobs.status("test-owner"))
    assert changed.generation != status.generation
    assert changed.status == "partial"
    assert preparation.demand.jobs.next_player(game.now()) == "test-owner"
    await routing.prepare(*pair)
    assert routing.router.route.await_count == 2


@pytest.mark.asyncio
async def test_reference_replacement_owns_rollback(game, database):
    game, preparation = build_prepared_game(game, database)
    offer = game.state_repository.list_offers()[0]
    pair = offer.origin.facility_uid, offer.destination.facility_uid
    await preparation.route_preparation.preparation.prepare(*pair)
    preparation.routes.bind((offer,))
    reference = require_value(preparation.routes.references.get(offer.id))
    invalid = replace(offer, id="missing-offer")
    with pytest.raises(PersistenceError):
        preparation.routes.bind((offer, invalid))
    assert preparation.routes.references.get(offer.id) == reference
    with pytest.raises(PersistenceError):
        preparation.routes.references.replace((("missing-offer", reference),))
    assert preparation.routes.references.get(offer.id) == reference
    before = game.state_repository.list_offers()
    with pytest.raises(PersistenceError), database.transaction():
        game.state_repository.remove_offer(offer.id)
        preparation.routes.bind((invalid,))
    assert game.state_repository.list_offers() == before
    assert preparation.routes.references.get(offer.id) == reference


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["next_player", "status", "finish"])
async def test_worker_recovers_entire_iteration(stage):
    status = PreparationStatus("p", "g", "partial", None)
    jobs = Mock()
    jobs.next_player.return_value = "owner"
    jobs.status.return_value = status
    getattr(jobs, stage).side_effect = [
        RuntimeError("database"),
        "owner"
        if stage == "next_player"
        else status
        if stage == "status"
        else None,
    ]
    process = AsyncMock()
    if stage == "finish":
        process.side_effect = [RuntimeError("batch"), None]
    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)
        if delay == 0:
            raise asyncio.CancelledError

    worker = MarketPreparationWorker(
        jobs,
        Mock(),
        lambda: 10,
        sleep=sleep,
    )
    worker.process = process
    worker.wake()
    with pytest.raises(asyncio.CancelledError):
        await worker._run()
    assert 60 in sleeps
    assert process.await_count == (2 if stage == "finish" else 1)


@pytest.mark.asyncio
async def test_worker_vanished_job_and_start_failure():
    jobs = Mock()
    jobs.next_player.return_value = "removed"
    jobs.status.return_value = None
    batches = Mock()
    worker = MarketPreparationWorker(jobs, batches, lambda: 0)
    await worker._iteration()
    batches.assert_not_called()
    with patch.object(worker, "_run", side_effect=RuntimeError("start")):
        with pytest.raises(RuntimeError, match="start"):
            await worker.start()
        with pytest.raises(RuntimeError, match="start"):
            await worker.close()
    assert worker._task is None


@pytest.mark.asyncio
async def test_batch_exhausts_deterministic_route_failures(game, database):
    game, preparation = build_prepared_game(game, database)
    batch = make_stock_batch(game, preparation)
    # Bound the structural pool so exhausting it is deterministic and fast.
    owned = game.state_repository.list_vehicles()
    fleet = game.market.candidates.resolve_fleet(owned)
    candidates = game.market.candidates.build(
        game.market_scope.resolve(owned), fleet
    )[:2]
    game.market.candidates.build = Mock(return_value=candidates)
    error = RoutingError("No path")
    error.category = "no_path"
    routing = preparation.route_preparation.preparation
    routing.router = AsyncMock()
    routing.router.route.side_effect = error
    preparation.demand.ensure()
    result = await batch.process()
    for _ in range(10):
        result = await batch.process()
        if result.status == "exhausted":
            break
    assert result.status == "exhausted"
    assert game.list_contracts() == []


def test_economy_audit_is_typed_and_reproducible():
    from random import Random

    from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
    from app.repositories.world_catalogue import SqliteWorldCatalogue
    from app.services.economy_audit import EconomyAuditService

    root = Path(__file__).resolve().parents[1]
    service = build_economy_audit(root, 20260925)
    assert isinstance(service.vehicles, SqliteVehicleCatalogue)
    assert isinstance(service.world, SqliteWorldCatalogue)
    models = service.vehicles.list_models()[:1]
    world = service.world.read()
    # Exercise compatible and incompatible rows with a bounded catalogue.
    profiles = world.market_profiles[:20]
    catalogue = Mock()
    catalogue.list_models.return_value = models
    worlds = Mock()
    worlds.read.return_value = replace(world, market_profiles=profiles)
    first = EconomyAuditService(catalogue, worlds, Random(20260925)).matrix()
    second = EconomyAuditService(catalogue, worlds, Random(20260925)).matrix()
    assert first == second
    assert any(row.compatible for row in first)
    assert any(not row.compatible for row in first)
    summary = summarize_economy(first)
    assert summary.models == 1
    assert summary.rows == len(first)
    assert summary.reference_min_margin >= 0.2
    with pytest.raises(FrozenInstanceError):
        setattr(first[0], "compatible", False)
