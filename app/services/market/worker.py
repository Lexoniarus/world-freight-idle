"""Lifespan-owned asynchronous preparation with durable player demand."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextvars import Context
from dataclasses import dataclass
from typing import Protocol

from app.domain.market_preparation import (
    PreparationBatchResult,
    PreparationStore,
)
from app.tracing import background_trace

LOGGER = logging.getLogger(__name__)


class PreparationBatch(Protocol):
    """Execute one bounded round without coupling the worker to planning."""

    async def process(self) -> PreparationBatchResult: ...


@dataclass(frozen=True, slots=True)
class PreparationWorkerTiming:
    """Configure scheduler waits without hiding real time in tests."""

    idle_wait_seconds: float = 60
    failure_retry_seconds: float = 60


class MarketPreparationWorker:
    """Own one cancellable fair-batch loop without inheriting request state."""

    def __init__(
        self,
        jobs: PreparationStore,
        batches: Callable[[str], PreparationBatch],
        clock: Callable[[], float],
        timing: PreparationWorkerTiming | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Inject scheduling storage and player lifecycle composition."""
        self.jobs = jobs
        self.batches = batches
        self.clock = clock
        self.timing = timing or PreparationWorkerTiming()
        self.sleep = sleep
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    def wake(self) -> None:
        """Signal newly committed work without polling the database."""
        if self._loop is None:
            self._wake.set()
            return
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is self._loop:
            self._wake.set()
        else:
            self._loop.call_soon_threadsafe(self._wake.set)

    @property
    def running(self) -> bool:
        """Report whether the lifespan currently owns an active task."""
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start exactly one owned loop in a fresh context."""
        if self._task is not None:
            raise RuntimeError("Preparation worker already started.")
        self._loop = asyncio.get_running_loop()
        self.wake()
        self._task = asyncio.create_task(self._run(), context=Context())
        await asyncio.sleep(0)
        if self._task.done():
            await self._task

    async def close(self) -> None:
        """Cancel and await owned work before provider resources close."""
        if self._task is not None:
            task, self._task = self._task, None
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            finally:
                self._loop = None

    async def _run(self) -> None:
        """Drain due work after events and recover without a second wait."""
        while True:
            try:
                await self._wait_for_work()
                self._wake.clear()
                await self._drain_due_jobs()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception(
                    "Market preparation scheduler failed",
                    extra={"event": "market.preparation_scheduler_failed"},
                )
                await self._recover_after_failure()

    async def _wait_for_work(self) -> None:
        """Wait for a wake signal or the bounded scheduler safety timer."""
        if self._wake.is_set():
            return
        waiter = asyncio.create_task(self._wake.wait())
        try:
            await asyncio.wait(
                (waiter,),
                timeout=self.timing.idle_wait_seconds,
            )
        finally:
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)

    async def _drain_due_jobs(self) -> None:
        """Yield fairly while processing every currently due job."""
        while await self._iteration():
            await self.sleep(0)

    async def _recover_after_failure(self) -> None:
        """Back off once, then make the next scheduler pass immediate."""
        await self.sleep(self.timing.failure_retry_seconds)
        self._wake.set()

    async def _iteration(self) -> bool:
        """Run one due job in its own trace and persist retry state."""
        user_id = self.jobs.next_player(self.clock())
        if user_id is None:
            return False
        status = self.jobs.status(user_id)
        if status is None:
            return True
        with background_trace(status.preparation_id):
            try:
                await self.process(user_id)
            except Exception:
                LOGGER.exception(
                    "Market preparation batch failed",
                    extra={
                        "event": "market.preparation_failed",
                        "data": {"preparation_id": status.preparation_id},
                    },
                )
                self.jobs.finish(
                    user_id,
                    status.generation,
                    "partial",
                    self.clock() + 60,
                    self.clock(),
                )
        return True

    async def process(self, user_id: str) -> None:
        """Execute a typed batch and persist its fenced scheduling result."""
        result = await self.batches(user_id).process()
        LOGGER.info(
            "Routing coverage preparation progress",
            extra={
                "event": "market.preparation_progress",
                "data": {
                    "structural_candidates": result.structural_count,
                    "relation_states": dict(result.relation_states),
                },
            },
        )
        self.jobs.finish(
            user_id,
            result.generation,
            result.status,
            result.retry_at,
            self.clock(),
        )
