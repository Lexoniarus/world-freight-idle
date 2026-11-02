"""Prepare reusable supply in bounded, resumable per-player rounds."""

from dataclasses import dataclass, replace

from app.domain.market import MarketCandidate
from app.domain.market_preparation import (
    PreparationBatchResult,
    required_relations,
)
from app.services.market.route_preparation import (
    MarketRoutePreparationService,
)
from app.services.market.stock.planning import (
    StockPlanningService,
    StockTarget,
)
from app.services.market.stock.publication import (
    StockPublicationService,
)
from app.services.market.stock.snapshot import (
    StockSnapshot,
    StockSnapshotReader,
)
from app.services.market.templates import MarketTemplateService
from app.services.market.vehicle_coverage import trade_key


@dataclass(slots=True)
class StockPreparationBatch:
    """Orchestrate selection, one provider relation and fenced publication."""

    publication: StockPublicationService
    snapshots: StockSnapshotReader
    planning: StockPlanningService
    templates: MarketTemplateService
    route_preparation: MarketRoutePreparationService

    async def process(self) -> PreparationBatchResult:
        """Advance one demand context, preserving fairness between players."""
        routes = self.publication.routes
        stock = self.publication.stores.offers
        snapshot = self.snapshots.read()
        pairs = required_relations(snapshot.candidates)
        with routes.readiness.reading(pairs):
            targets = self.planning.targets(
                snapshot.demands,
                snapshot.candidates,
                snapshot.ready,
                snapshot.usable_offers,
            )
            selected = self._select(snapshot, targets)
            waiting = selected is None and self._waiting(targets)
        if selected is None:
            self.publication.publish(snapshot, (), ())
            return self._result(
                snapshot,
                "partial" if waiting else "exhausted" if targets else "ready",
                60,
            )
        target, candidate = selected
        with self.publication.unit.transaction():
            if not self.publication.guard():
                return self._result(snapshot, "partial", 1)
            stock.checkpoint(target.key, trade_key(candidate))
        ready = self._ready(snapshot, candidate)
        if not ready:
            await self.route_preparation.prepare(
                (candidate,),
                limit=1,
            )
            if not self.publication.unchanged(snapshot):
                return self._result(snapshot, "partial", 0)
            newly_ready = routes.ready_candidates((candidate,))
            ready = bool(newly_ready)
            fresh = self.planning.targets(
                snapshot.demands,
                snapshot.candidates,
                tuple((*snapshot.ready, *newly_ready)),
                snapshot.usable_offers,
            )
            remaining = next((t for t in fresh if t.key == target.key), None)
            if remaining is None:
                self.publication.publish(snapshot, (), ())
                return self._result(snapshot, "partial", 0)
            target = remaining
        if ready:
            templates, issued = self.templates.materialize(
                snapshot.usable_templates,
                snapshot.used,
                snapshot.bindings,
                target,
                candidate,
            )
            self.publication.publish(
                snapshot,
                templates,
                issued,
                target.key,
            )
        else:
            self.publication.publish(snapshot, (), ())
        return self._result(snapshot, "partial", 0)

    def _select(
        self,
        snapshot: StockSnapshot,
        targets: tuple[StockTarget, ...],
    ) -> tuple[StockTarget, MarketCandidate] | None:
        """Skip failed/backing-off work without starving other contexts."""
        stock = self.publication.stores.offers
        for target in self.planning.order(targets, stock.cursor()):
            choices = tuple(c for c in target.choices if self._runnable(c))
            if not choices:
                continue
            ready = tuple(c for c in choices if self._ready(snapshot, c))
            if ready:
                choices = ready
            return target, self.planning.choose(
                replace(target, choices=choices),
                stock.pending(target.key),
                snapshot.usable_templates,
            )
        return None

    def _runnable(self, candidate: MarketCandidate) -> bool:
        """Respect shared negative evidence and provider retry deadlines."""
        routes = self.publication.routes
        for pair in required_relations((candidate,)):
            current = routes.readiness.current(*pair)
            if current is not None and (
                current.status == "deterministic_failure"
                or (
                    current.retry_at is not None
                    and current.retry_at
                    > self.publication.player_demand.clock()
                )
            ):
                return False
        return True

    def _ready(
        self, snapshot: StockSnapshot, candidate: MarketCandidate
    ) -> bool:
        """Require a ready delivery and the context's real approach."""
        vehicle_id = candidate.vehicles[0].vehicle.vehicle_id
        return (trade_key(candidate), vehicle_id) in snapshot.ready_contexts

    def _waiting(self, targets: tuple[StockTarget, ...]) -> bool:
        """Keep provider backoff distinct from exhausted road coverage."""
        readiness = self.publication.routes.readiness
        return any(
            current.status == "transient_failure"
            for target in targets
            for candidate in target.choices
            for pair in required_relations((candidate,))
            if (current := readiness.current(*pair)) is not None
        )

    def _result(
        self,
        snapshot: StockSnapshot,
        status: str,
        delay: float,
    ) -> PreparationBatchResult:
        """Return scheduling facts through the existing worker contract."""
        return PreparationBatchResult(
            snapshot.status.generation,
            status,
            self.publication.player_demand.clock() + delay,
            len(snapshot.candidates),
            (),
        )
