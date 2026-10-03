"""Lifespan-owned asynchronous preparation with durable player demand."""

import asyncio
import logging
from collections.abc import Callable
from contextvars import Context
from functools import partial
from typing import Protocol

from app.domain.market_preparation import PreparationStore
from app.services.preparation_batch import PreparationBatchResult
from app.services.preparation_lease import PreparationLease
from app.tracing import background_trace

LOGGER = logging.getLogger(__name__)


class PreparationBatch(Protocol):
    """Execute one bounded round without coupling the worker to planning."""

    async def process(self) -> PreparationBatchResult: ...


class MarketPreparationWorker:
    """Own one cancellable fair-batch loop without inheriting request state."""

    def __init__(
        self,
        jobs: PreparationStore,
        batches: Callable[[str], PreparationBatch],
        clock: Callable[[], float],
        lease: PreparationLease | None = None,
        background: PreparationBatch | None = None,
    ) -> None:
        """Inject scheduling storage and player lifecycle composition."""
        self.jobs = jobs
        self.batches = batches
        self.clock = clock
        self.lease = lease
        self.background = background
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start exactly one owned loop in a fresh context."""
        if self._task is not None:
            raise RuntimeError("Preparation worker already started.")
        self._task = asyncio.create_task(self._run(), context=Context())
        await asyncio.sleep(0)
        if self._task.done():
            await self._task

    async def close(self) -> None:
        """Cancel and await owned work before provider resources close."""
        try:
            if self._task is not None:
                task, self._task = self._task, None
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        finally:
            if self.lease is not None:
                self.lease.close()

    async def _run(self) -> None:
        """Recover the complete iteration, including scheduler failures."""
        while True:
            try:
                await self._iteration()
            except Exception:
                LOGGER.exception(
                    "Market preparation scheduler failed",
                    extra={"event": "market.preparation_scheduler_failed"},
                )
                await asyncio.sleep(60)
            await asyncio.sleep(0)

    async def _iteration(self) -> None:
        """Run one due job in its own trace and persist retry state."""
        user_id = self.jobs.next_player(self.clock())
        if user_id is None:
            if self.background is not None and not self.jobs.has_incomplete():
                await self._process_background()
                return
            await asyncio.sleep(1)
            return
        status = self.jobs.status(user_id)
        if status is None:
            return
        with background_trace(status.preparation_id):
            try:
                if self.lease is None:
                    await self.process(user_id)
                elif not await self.lease.run(partial(self.process, user_id)):
                    await asyncio.sleep(1)
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

    async def _process_background(self) -> None:
        """Use idle worker capacity for one bounded global stock round."""
        background = self.background
        assert background is not None
        with background_trace("global-market-stock"):
            if self.lease is not None:
                if not await self.lease.run(background.process):
                    await asyncio.sleep(1)
                return
            result = await background.process()
            LOGGER.info(
                "Global market preparation round completed",
                extra={
                    "event": "market.global_preparation_completed",
                    "data": {
                        "status": result.status,
                        "structural_candidates": result.structural_count,
                    },
                },
            )
            if result.status == "ready":
                await asyncio.sleep(1)

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
