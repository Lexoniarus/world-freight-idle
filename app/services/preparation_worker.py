"""Lifespan-owned asynchronous preparation with durable player demand."""

import asyncio
import logging
from collections import Counter
from collections.abc import Callable
from contextvars import Context

from app.domain.market_preparation import PreparationStore
from app.services.market_lifecycle import MarketLifecycleService
from app.tracing import background_trace

LOGGER = logging.getLogger(__name__)


class MarketPreparationWorker:
    """Own one cancellable fair-batch loop without inheriting request state."""

    def __init__(
        self,
        jobs: PreparationStore,
        lifecycle: Callable[[str], MarketLifecycleService],
        clock: Callable[[], float],
    ) -> None:
        """Inject scheduling storage and player lifecycle composition."""
        self.jobs = jobs
        self.lifecycle = lifecycle
        self.clock = clock
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
        if self._task is not None:
            task, self._task = self._task, None
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        """Process due batches fairly and isolate failures with backoff."""
        while True:
            user_id = self.jobs.next_player(self.clock())
            if user_id is None:
                await asyncio.sleep(1)
                continue
            status = self.jobs.status(user_id)
            assert status is not None
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
            await asyncio.sleep(0)

    async def process(self, user_id: str) -> None:
        """Prepare missing coverage and re-read state before publication."""
        lifecycle = self.lifecycle(user_id)
        preparation = lifecycle.preparation
        assert preparation is not None
        offers = tuple(lifecycle.refresh())
        status = self.jobs.status(user_id)
        assert status is not None
        owned = lifecycle.unit_of_work.repository.list_vehicles()
        fleet = lifecycle.generator.candidates.resolve_fleet(owned)
        cities = lifecycle.scope.resolve(owned)
        candidates = lifecycle.generator.candidates.build(cities, fleet)
        states = {
            pair: preparation.readiness.current(*pair)
            for pair in dict.fromkeys(
                (c.trade.origin.facility_uid, c.trade.destination.facility_uid)
                for c in candidates
            )
        }
        LOGGER.info(
            "Routing coverage preparation progress",
            extra={
                "event": "market.preparation_progress",
                "data": {
                    "preparation_id": status.preparation_id,
                    "structural_candidates": len(candidates),
                    "relation_states": dict(
                        Counter(
                            relation.status
                            if relation
                            else "unchecked_or_stale"
                            for relation in states.values()
                        )
                    ),
                },
            },
        )
        usable = tuple(
            c
            for c in candidates
            if (
                relation := states[
                    c.trade.origin.facility_uid,
                    c.trade.destination.facility_uid,
                ]
            )
            is None
            or relation.status != "deterministic_failure"
        )
        plan = lifecycle.generator.coverage.plan(cities, usable, offers)
        published_pairs = {
            (o.origin.facility_uid, o.destination.facility_uid) for o in offers
        }
        needed = tuple(
            dict.fromkeys(
                (
                    *plan.selected,
                    *(
                        c
                        for c in usable
                        if (
                            c.trade.origin.facility_uid,
                            c.trade.destination.facility_uid,
                        )
                        in published_pairs
                    ),
                )
            )
        )
        complete, retry_at = await preparation.prepare_batch(needed, fleet)
        lifecycle.refresh()
        outcome = "partial"
        if complete and not plan.selected:
            unmet = lifecycle.generator.coverage.plan(
                cities, candidates, offers
            )
            outcome = "exhausted" if unmet.selected else "ready"
        self.jobs.finish(
            user_id,
            status.generation,
            outcome,
            retry_at,
            self.clock(),
        )
