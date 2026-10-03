"""Prepare player-independent market templates after concrete demand."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from time import perf_counter

from app.domain.market import MarketCandidate
from app.domain.market_preparation import delivery_relations
from app.domain.market_stock import (
    MarketDemand,
    MarketTemplateStore,
    PreparedTemplate,
)
from app.domain.state_ports import TransactionBoundary
from app.services.market_candidates import MarketCandidateService
from app.services.market_demand import MarketDemandResolver
from app.services.market_templates import MarketTemplateService
from app.services.preparation_batch import PreparationBatchResult
from app.services.routing_readiness import RoutingReadinessService
from app.services.stock_planning import StockPlanningService, StockTarget

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GlobalStockContext:
    """Identify one player-independent city/model/distance deficit."""

    key: str
    demand: MarketDemand
    band: str


@dataclass(slots=True)
class GlobalStockPreparationBatch:
    """Advance one global city/model/band deficit without player state."""

    candidates: MarketCandidateService
    demand: MarketDemandResolver
    planning: StockPlanningService
    templates: MarketTemplateService
    readiness: RoutingReadinessService
    store: MarketTemplateStore
    transactions: TransactionBoundary
    clock: Callable[[], float]
    guard: Callable[[], bool]
    cursor: str = field(default="", init=False)

    async def process(self) -> PreparationBatchResult:
        """Select one deficit, prepare one pair and publish reusable stock."""
        started = perf_counter()
        context = self._next_context()
        if context is None:
            return self._result("ready", 60, 0)
        self.cursor = context.key
        built_at = perf_counter()
        target, candidates, ready, templates = self._plan(context)
        pairs = delivery_relations(candidates)
        if target is None:
            self._log(
                context.key, len(candidates), len(pairs), started, built_at
            )
            return self._result("partial", 0, len(candidates))
        choice = self._choose(target, templates)
        if choice is None:
            self._log(
                context.key, len(candidates), len(pairs), started, built_at
            )
            return self._result("partial", 60, len(candidates))
        if choice not in ready and not await self._prepare(choice):
            self._log(
                context.key, len(candidates), len(pairs), started, built_at
            )
            return self._result("partial", 0, len(candidates))
        self._publish(context, target, choice, templates)
        self._log(context.key, len(candidates), len(pairs), started, built_at)
        return self._result("partial", 0, len(candidates))

    def _next_context(self) -> GlobalStockContext | None:
        """Rotate deterministically over every global stock deficit."""
        demands = self.demand.catalogue(self.clock())
        counts = {
            (level.city_uid, level.model_id, level.distance_band): level.count
            for level in self.store.levels()
        }
        contexts = tuple(
            GlobalStockContext(
                f"{item.vehicle.city_uid}:{item.vehicle.model_id}:{band}",
                item,
                band,
            )
            for item in demands
            for band in ("short", "medium", "long")
            if counts.get(
                (item.vehicle.city_uid, item.vehicle.model_id, band), 0
            )
            < self.planning.policy.reserve_per_band
        )
        if not contexts:
            return None
        return next(
            (entry for entry in contexts if entry.key > self.cursor),
            contexts[0],
        )

    def _plan(
        self, context: GlobalStockContext
    ) -> tuple[
        StockTarget | None,
        tuple[MarketCandidate, ...],
        tuple[MarketCandidate, ...],
        tuple[PreparedTemplate, ...],
    ]:
        """Build candidates only for the selected global context."""
        selected = context.demand
        candidates = tuple(
            candidate
            for candidate in self.candidates.build(
                (selected.vehicle.city_uid,), (selected.vehicle,)
            )
            if candidate.distance_profile.distance_band == context.band
        )
        pairs = delivery_relations(candidates)
        with self.readiness.reading(pairs):
            ready = tuple(
                candidate
                for candidate in candidates
                if self.readiness.ready(
                    candidate.trade.origin.facility_uid,
                    candidate.trade.destination.facility_uid,
                )
                is not None
            )
        templates = self.store.scoped_templates(
            ((selected.vehicle.city_uid, selected.vehicle.model_id),)
        )
        targets = self.planning.targets(
            (selected,), candidates, ready, (), templates
        )
        target = next(
            (item for item in targets if item.band == context.band), None
        )
        return target, candidates, ready, templates

    def _choose(
        self,
        target: StockTarget,
        templates: tuple[PreparedTemplate, ...],
    ) -> MarketCandidate | None:
        """Choose one runnable trade while preserving planning fairness."""
        with self.readiness.reading(delivery_relations(target.choices)):
            runnable = tuple(
                candidate
                for candidate in target.choices
                if self._runnable(candidate)
            )
        if not runnable:
            return None
        choice = self.planning.choose(
            target,
            None,
            templates,
        )
        if choice not in runnable:
            choice = self.planning.choose(
                replace(target, choices=runnable),
                None,
                templates,
            )
        return choice

    async def _prepare(self, candidate: MarketCandidate) -> bool:
        """Prepare and verify one bidirectional delivery relation."""
        origin = candidate.trade.origin.facility_uid
        destination = candidate.trade.destination.facility_uid
        await self.readiness.prepare(origin, destination)
        with self.readiness.reading(((origin, destination),)):
            return self.readiness.ready(origin, destination) is not None

    def _publish(
        self,
        context: GlobalStockContext,
        target: StockTarget,
        candidate: MarketCandidate,
        templates: tuple[PreparedTemplate, ...],
    ) -> None:
        """Atomically publish reusable terms without issuing player offers."""
        created, issued = self.templates.materialize(
            templates,
            frozenset(),
            {},
            target,
            candidate,
        )
        assert not issued
        with self.transactions.transaction():
            if not self.guard() or self._filled(context.demand, context.band):
                return
            for template in created:
                self.store.add(template)

    def _filled(self, demand: MarketDemand, band: str) -> bool:
        """Fence publication against a concurrently filled global context."""
        key = (demand.vehicle.city_uid, demand.vehicle.model_id, band)
        return any(
            (level.city_uid, level.model_id, level.distance_band) == key
            and level.count >= self.planning.policy.reserve_per_band
            for level in self.store.levels()
        )

    def _runnable(self, candidate: MarketCandidate) -> bool:
        """Respect shared negative evidence and provider retry deadlines."""
        origin = candidate.trade.origin.facility_uid
        destination = candidate.trade.destination.facility_uid
        relation = self.readiness.current(origin, destination)
        return relation is None or (
            relation.status != "deterministic_failure"
            and (
                relation.retry_at is None or relation.retry_at <= self.clock()
            )
        )

    def _result(
        self, status: str, delay: float, candidates: int
    ) -> PreparationBatchResult:
        """Return worker-compatible scheduling facts for global supply."""
        return PreparationBatchResult(
            "global-market-stock",
            status,
            self.clock() + delay,
            candidates,
            (),
        )

    @staticmethod
    def _log(
        context: str,
        candidates: int,
        relations: int,
        started: float,
        built_at: float,
    ) -> None:
        """Record bounded phase timings without player identities."""
        LOGGER.info(
            "Global market stock preparation progress",
            extra={
                "event": "market.global_preparation_progress",
                "data": {
                    "priority": 5,
                    "context": context,
                    "candidate_count": candidates,
                    "relation_count": relations,
                    "planning_ms": round((built_at - started) * 1000, 2),
                    "round_ms": round((perf_counter() - started) * 1000, 2),
                },
            },
        )
