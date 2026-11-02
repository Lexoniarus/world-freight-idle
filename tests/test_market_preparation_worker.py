"""Background market preparation scheduling, backoff and shutdown."""

from unittest.mock import Mock

import pytest

from app.services.market.worker import (
    MarketPreparationWorker,
    PreparationWorkerTiming,
)
from tests.support.market import (
    build_prepared_game,
    make_stock_batch,
    require_value,
)


@pytest.mark.asyncio
async def test_worker_fills_ready_market(
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


@pytest.mark.asyncio
async def test_worker_owns_one_task_and_closes_idempotently():
    jobs = Mock()
    jobs.next_player.return_value = None
    worker = MarketPreparationWorker(
        jobs,
        Mock(),
        lambda: 0,
        timing=PreparationWorkerTiming(idle_wait_seconds=0.01),
    )
    await worker.start()
    assert worker.running
    worker.wake()
    with pytest.raises(RuntimeError):
        await worker.start()
    await worker.close()
    await worker.close()
    assert not worker.running
