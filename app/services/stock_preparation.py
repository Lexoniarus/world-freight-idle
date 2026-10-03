"""Prepare reusable supply in bounded, resumable per-player rounds."""

from dataclasses import dataclass, replace

from app.domain.market import MarketCandidate
from app.domain.market_preparation import required_relations
from app.services.market_templates import MarketTemplateService
from app.services.preparation_batch import PreparationBatchResult
from app.services.stock_planning import StockPlanningService, StockTarget
from app.services.stock_publication import (
    StockPublicationService,
    StockSnapshot,
)
from app.services.vehicle_coverage import trade_key


@dataclass(slots=True)
class StockPreparationBatch:
    """Orchestrate selection, one provider relation and fenced publication."""

    publication: StockPublicationService
    planning: StockPlanningService
    templates: MarketTemplateService

    async def process(self) -> PreparationBatchResult:
        """Advance one demand context, preserving fairness between players."""
        prep = self.publication.preparation
        stock = prep.stock
        assert stock is not None
        snapshot = self.publication.read()
        pairs = required_relations(snapshot.candidates)
        with prep.readiness.reading(pairs):
            targets = self.planning.targets(
                snapshot.demands,
                snapshot.candidates,
                snapshot.ready,
                snapshot.usable_offers,
                snapshot.usable_templates,
                snapshot.used,
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
        if not self._ready(snapshot, candidate):
            await prep.prepare_batch(
                (candidate,),
                (target.demand.vehicle,),
                limit=1,
            )
            current = self.publication.read()
            if (
                current.owned != snapshot.owned
                or current.offers != snapshot.offers
                or current.arrivals != snapshot.arrivals
                or current.status != snapshot.status
                or current.reference != snapshot.reference
            ):
                return self._result(current, "partial", 0)
            snapshot = current
            fresh = self.planning.targets(
                snapshot.demands,
                snapshot.candidates,
                snapshot.ready,
                snapshot.usable_offers,
                snapshot.usable_templates,
                snapshot.used,
            )
            remaining = next((t for t in fresh if t.key == target.key), None)
            if remaining is None:
                self.publication.publish(snapshot, (), ())
                return self._result(snapshot, "partial", 0)
            target = remaining
        if self._ready(snapshot, candidate):
            templates, issued = self.templates.materialize(
                snapshot.usable_templates,
                snapshot.used,
                snapshot.bindings,
                target,
                candidate,
            )
            self.publication.publish(snapshot, templates, issued)
        else:
            self.publication.publish(snapshot, (), ())
        return self._result(snapshot, "partial", 0)

    def _select(
        self,
        snapshot: StockSnapshot,
        targets: tuple[StockTarget, ...],
    ) -> tuple[StockTarget, MarketCandidate] | None:
        """Skip failed/backing-off work without starving other contexts."""
        prep = self.publication.preparation
        stock = prep.stock
        assert stock is not None
        for target in self.planning.order(targets, stock.cursor()):
            choices = tuple(c for c in target.choices if self._runnable(c))
            if not choices:
                continue
            ready = tuple(c for c in choices if self._ready(snapshot, c))
            if ready:
                choices = ready
            known = {
                (
                    t.offer.origin.facility_uid,
                    t.offer.destination.facility_uid,
                    t.offer.cargo.nhm_row_id,
                )
                for t in snapshot.usable_templates
                if t.model_id == target.demand.vehicle.model_id
                and t.template_id not in snapshot.used
                and t.template_id not in snapshot.bindings
            }
            reusable = tuple(c for c in choices if trade_key(c) in known)
            narrowed = replace(target, choices=reusable or choices)
            return target, self.planning.choose(
                narrowed,
                stock.pending(target.key),
                snapshot.usable_templates,
            )
        return None

    def _runnable(self, candidate: MarketCandidate) -> bool:
        """Respect shared negative evidence and provider retry deadlines."""
        prep = self.publication.preparation
        for pair in required_relations((candidate,)):
            current = prep.readiness.current(*pair)
            if current is not None and (
                current.status == "deterministic_failure"
                or (
                    current.retry_at is not None
                    and current.retry_at > prep.clock()
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
        readiness = self.publication.preparation.readiness
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
            self.publication.preparation.clock() + delay,
            len(snapshot.candidates),
            (),
        )
