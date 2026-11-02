"""Scheduler recovery at database and lifecycle boundaries."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.domain.market_preparation import PreparationStatus
from app.services.market.worker import MarketPreparationWorker


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
    assert not worker.running
