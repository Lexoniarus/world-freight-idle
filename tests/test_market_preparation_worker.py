"""Background market preparation scheduling, backoff and shutdown."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.errors import RoutingError
from app.services.preparation_worker import (
    MarketPreparationWorker,
    PreparationWorkerTiming,
)
from tests.support.market import (
    build_prepared_game,
    make_stock_batch,
    require_value,
)
from tests.support.routing import (
    FakeRouter,
    FakeRoutingAnchorResolver,
    RoutingTestHarness,
)


@pytest.mark.asyncio
async def test_worker_fills_ready_market_and_owns_shutdown(
    synthetic_game_context, database
):
    prepared_context, preparation = build_prepared_game(
        synthetic_game_context, database
    )
    synthetic_game = prepared_context.service
    batch = make_stock_batch(synthetic_game, preparation)
    preparation.demand.ensure()
    worker = MarketPreparationWorker(
        preparation.demand.jobs,
        lambda user: batch,
        synthetic_game.now,
        timing=PreparationWorkerTiming(idle_wait_seconds=0.01),
    )
    assert (
        preparation.demand.jobs.next_player(synthetic_game.now())
        == "test-owner"
    )
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
    assert synthetic_game.list_contracts()
    assert all(
        o.eligible_vehicle_ids
        for o in synthetic_game.contract_choices(
            synthetic_game.list_contracts()
        )
    )
    await worker.start()
    assert worker.running
    worker.wake()
    with pytest.raises(RuntimeError):
        await worker.start()
    await asyncio.sleep(0.03)
    await worker.close()
    await worker.close()
    assert not worker.running


@pytest.mark.asyncio
async def test_preparation_failures_backoff_fencing_and_worker_cleanup(
    synthetic_game_context,
    database,
):
    prepared_context, preparation = build_prepared_game(
        synthetic_game_context, database
    )
    synthetic_game = prepared_context.service
    readiness = RoutingTestHarness(
        preparation.routes.readiness,
        preparation.route_preparation.preparation,
    )
    owned = synthetic_game.state_repository.list_vehicles()
    fleet = synthetic_game_context.market.candidates.resolve_fleet(owned)
    pool = synthetic_game_context.market.candidates.build(
        synthetic_game_context.market_scope.resolve(owned), fleet
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
    with patch.object(
        type(preparation.route_preparation.preparation),
        "prepare",
        new=AsyncMock(return_value=None),
    ):
        complete, retry = await preparation.route_preparation.prepare(
            (candidate,)
        )
        assert not complete and retry is not None
    readiness.router = FakeRouter()
    with patch.object(readiness.store, "renew", return_value=False):
        assert await readiness.prepare(*pair) is None
    batch = make_stock_batch(synthetic_game, preparation)
    preparation.demand.ensure()
    worker = MarketPreparationWorker(
        preparation.demand.jobs, lambda user: batch, synthetic_game.now
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
        preparation.demand.jobs, lambda user: batch, synthetic_game.now
    )
    with patch.object(
        preparation.demand.jobs,
        "next_player",
        side_effect=RuntimeError("startup"),
    ):
        await failed_worker.start()
        assert failed_worker.running
        await failed_worker.close()
