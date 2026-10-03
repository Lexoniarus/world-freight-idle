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
from app.services.preparation_batch import PreparationBatchResult
from app.services.preparation_worker import MarketPreparationWorker
from tests.test_market_preparation import (
    bind_preparation,
    make_batch,
    require_value,
)


@pytest.mark.asyncio
async def test_worker_pauses_global_stock_for_every_incomplete_player():
    jobs = Mock()
    jobs.next_player.return_value = None
    jobs.has_incomplete.return_value = True
    background = Mock()
    background.process = AsyncMock(
        return_value=PreparationBatchResult("global", "partial", 0, 1, ())
    )
    worker = MarketPreparationWorker(
        jobs,
        Mock(),
        lambda: 10,
        background=background,
    )
    with patch(
        "app.services.preparation_worker.asyncio.sleep", new=AsyncMock()
    ):
        await worker._iteration()
        background.process.assert_not_awaited()
        jobs.has_incomplete.return_value = False
        await worker._iteration()
        background.process.assert_awaited_once()
        background.process.return_value = PreparationBatchResult(
            "global", "ready", 70, 0, ()
        )
        await worker._iteration()
        assert background.process.await_count == 2
        jobs.next_player.return_value = "owner"
        jobs.status.return_value = PreparationStatus(
            "player", "generation", "partial", None
        )
        with patch.object(worker, "process", new=AsyncMock()) as process:
            await worker._iteration()
            process.assert_awaited_once_with("owner")
        assert background.process.await_count == 2

        lease = Mock()
        lease.run = AsyncMock(side_effect=(False, True))
        leased = MarketPreparationWorker(
            jobs,
            Mock(),
            lambda: 10,
            lease=lease,
            background=background,
        )
        jobs.next_player.return_value = None
        await leased._iteration()
        await leased._iteration()
        assert lease.run.await_count == 2


@pytest.mark.asyncio
async def test_exhausted_negative_demand_requeues_after_revision(
    game, database
):
    preparation = bind_preparation(game, database)
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
    readiness = preparation.readiness
    error = RoutingError("No path")
    error.category = "no_path"
    readiness.router = AsyncMock()
    readiness.router.route.side_effect = error
    await readiness.prepare(*pair)
    preparation.prepare_publication((candidate,), fleet)
    status = require_value(preparation.jobs.status("test-owner"))
    preparation.jobs.finish(
        "test-owner", status.generation, "exhausted", None, game.now()
    )
    preparation.prepare_publication((candidate,), fleet)
    assert preparation.jobs.next_player(game.now()) is None
    readiness.provider_revision = lambda: "new-graph"
    preparation.prepare_publication((candidate,), fleet)
    changed = require_value(preparation.jobs.status("test-owner"))
    assert changed.generation != status.generation
    assert changed.status == "partial"
    assert preparation.jobs.next_player(game.now()) == "test-owner"
    assert preparation.prepare_publication((candidate,), fleet) == ()
    await readiness.prepare(*pair)
    assert readiness.router.route.await_count == 2


@pytest.mark.asyncio
async def test_reference_replacement_owns_rollback(game, database):
    preparation = bind_preparation(game, database)
    offer = game.state_repository.list_offers()[0]
    pair = offer.origin.facility_uid, offer.destination.facility_uid
    await preparation.readiness.prepare(*pair)
    preparation.bind((offer,))
    reference = require_value(preparation.references.get(offer.id))
    invalid = replace(offer, id="missing-offer")
    with pytest.raises(PersistenceError):
        preparation.bind((offer, invalid))
    assert preparation.references.get(offer.id) == reference
    with pytest.raises(PersistenceError):
        preparation.references.replace((("missing-offer", reference),))
    assert preparation.references.get(offer.id) == reference
    before = game.state_repository.list_offers()
    with pytest.raises(PersistenceError), database.transaction():
        game.state_repository.remove_offer(offer.id)
        preparation.bind((invalid,))
    assert game.state_repository.list_offers() == before
    assert preparation.references.get(offer.id) == reference


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
    worker = MarketPreparationWorker(jobs, Mock(), lambda: 10)
    process = AsyncMock()
    worker.process = process
    if stage == "finish":
        process.side_effect = [RuntimeError("batch"), None]
    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)
        if process.await_count >= (2 if stage == "finish" else 1):
            raise asyncio.CancelledError

    with patch("app.services.preparation_worker.asyncio.sleep", sleep):
        with pytest.raises(asyncio.CancelledError):
            await worker._run()
    assert 60 in sleeps
    assert process.await_count >= 1


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
async def test_batch_exhaustion_and_generation_change(game, database):
    preparation = bind_preparation(game, database)
    batch = make_batch(game, preparation)
    # Bound the structural pool so exhausting it is deterministic and fast.
    owned = game.state_repository.list_vehicles()
    fleet = game.market.candidates.resolve_fleet(owned)
    candidates = game.market.candidates.build(
        game.market_scope.resolve(owned), fleet
    )[:2]
    game.market.candidates.build = Mock(return_value=candidates)
    error = RoutingError("No path")
    error.category = "no_path"
    preparation.readiness.router = AsyncMock()
    preparation.readiness.router.route.side_effect = error
    result = await batch.process()
    for _ in range(10):
        result = await batch.process()
        if result.status == "exhausted":
            break
    assert result.status == "exhausted"
    assert game.list_contracts() == []
    plan = batch.plan()
    with patch.object(
        batch,
        "plan",
        side_effect=[
            plan,
            replace(plan, generation="changed", exhausted=False),
        ],
    ):
        changed = await batch.process()
    assert changed.generation == plan.generation
    assert changed.status == "partial"


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
