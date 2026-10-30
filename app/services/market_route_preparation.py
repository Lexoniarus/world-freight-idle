"""Bounded provider preparation for reusable market route evidence."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from app.domain.market import MarketCandidate
from app.domain.market_preparation import required_relations
from app.services.routing_readiness import RoutingReadinessService

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MarketRoutePreparationService:
    """Prepare missing route evidence outside player read transactions."""

    readiness: RoutingReadinessService
    clock: Callable[[], float]

    async def prepare(
        self,
        candidates: tuple[MarketCandidate, ...],
        limit: int = 4,
    ) -> tuple[bool, float | None]:
        """Prepare a bounded relation batch with explicit retry timing."""
        pairs = required_relations(candidates)
        count = 0
        waiting = False
        retry_at = None
        started = perf_counter()
        for origin, destination in pairs:
            current = self.readiness.current(origin, destination)
            if current and current.status in {
                "ready",
                "deterministic_failure",
            }:
                continue
            if (
                current
                and current.retry_at
                and current.retry_at > self.clock()
            ):
                waiting = True
                retry_at = min(retry_at or current.retry_at, current.retry_at)
                continue
            if count >= limit:
                waiting = True
                retry_at = self.clock()
                break
            count += 1
            result = await self.readiness.prepare(origin, destination)
            if result is None or result.status == "transient_failure":
                waiting = True
                next_try = (result.retry_at if result else None) or (
                    self.clock() + 1
                )
                retry_at = min(retry_at or next_try, next_try)
        LOGGER.info(
            "Market routing preparation phase completed",
            extra={
                "event": "market.provider_phase",
                "data": {
                    "relation_count": len(pairs),
                    "provider_request_count": count,
                    "provider_ms": round(
                        (perf_counter() - started) * 1000,
                        3,
                    ),
                },
            },
        )
        return not waiting, retry_at
