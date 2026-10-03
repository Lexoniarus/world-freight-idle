"""Prepare reusable supply in bounded, resumable per-player rounds."""

import logging
from dataclasses import dataclass, replace
from time import perf_counter

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

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class StockPreparationBatch:
    """Orchestrate selection, one provider relation and fenced publication."""

    publication: StockPublicationService
    planning: StockPlanningService
    templates: MarketTemplateService

    async def process(self) -> PreparationBatchResult:
        """Advance one demand context, preserving fairness between players."""
        started = perf_counter()
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
            self.publication.publish(
                snapshot,
                (),
                (),
                tuple(target.key for target in targets),
            )
            self._log(snapshot, None, started, 0.0)
            return self._result(
                snapshot,
                "partial" if waiting else "exhausted" if targets else "ready",
                60,
            )
        target, candidate = selected
        provider_started = perf_counter()
        was_ready = self._ready(snapshot, candidate)
        if not was_ready:
            with self.publication.unit.transaction():
                if not self.publication.guard():
                    return self._result(snapshot, "partial", 1)
                stock.checkpoint(target.key, trade_key(candidate))
            await prep.prepare_batch(
                (candidate,),
                (target.demand.vehicle,),
                limit=1,
            )
        provider_ms = (perf_counter() - provider_started) * 1000
        current_ready = prep.ready_candidates((candidate,))
        ready = was_ready or bool(current_ready)
        if ready:
            ready_candidates = tuple(
                {
                    trade_key(item): item
                    for item in (*snapshot.ready, *current_ready)
                }.values()
            )
            fresh_targets = self.planning.targets(
                snapshot.demands,
                snapshot.candidates,
                ready_candidates,
                snapshot.usable_offers,
                snapshot.usable_templates,
                snapshot.used,
            )
            remaining = next(
                (item for item in fresh_targets if item.key == target.key),
                None,
            )
            if remaining is None:
                self.publication.publish(
                    snapshot,
                    (),
                    (),
                    tuple(item.key for item in fresh_targets),
                    target.key,
                )
                self._log(snapshot, target, started, provider_ms)
                return self._result(snapshot, "partial", 0)
            target = remaining
            if not was_ready and trade_key(candidate) in self._bound_trades(
                snapshot, target
            ):
                self.publication.publish(
                    snapshot,
                    (),
                    (),
                    tuple(item.key for item in fresh_targets),
                    target.key,
                )
                self._log(snapshot, target, started, provider_ms)
                return self._result(snapshot, "partial", 0)
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
                tuple(item.key for item in fresh_targets),
                target.key,
            )
        else:
            self.publication.publish(
                snapshot,
                (),
                (),
                tuple(item.key for item in targets),
            )
        self._log(snapshot, target, started, provider_ms)
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
            bound = self._bound_trades(snapshot, target)
            unready_bound = tuple(
                candidate
                for candidate in choices
                if trade_key(candidate) in bound
                and not self._ready(snapshot, candidate)
            )
            if unready_bound:
                choices = unready_bound
            else:
                choices = self.planning.preferred(
                    replace(target, choices=choices),
                    snapshot.usable_templates,
                )
                ready = tuple(c for c in choices if self._ready(snapshot, c))
                if ready:
                    choices = ready
            if not any(self._ready(snapshot, c) for c in choices):
                missing = {
                    trade_key(candidate): sum(
                        prep.readiness.ready(*pair) is None
                        for pair in required_relations((candidate,))
                    )
                    for candidate in choices
                }
                minimum = min(missing.values())
                choices = tuple(
                    candidate
                    for candidate in choices
                    if missing[trade_key(candidate)] == minimum
                )
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

    @staticmethod
    def _bound_trades(
        snapshot: StockSnapshot,
        target: StockTarget,
    ) -> frozenset[tuple[str, str, int]]:
        """Identify persisted private trades that need route recovery first."""
        offer_ids = {offer.id for offer in snapshot.usable_offers}
        return frozenset(
            (
                template.offer.origin.facility_uid,
                template.offer.destination.facility_uid,
                template.offer.cargo.nhm_row_id,
            )
            for template in snapshot.usable_templates
            if template.city_uid == target.demand.vehicle.city_uid
            and template.model_id == target.demand.vehicle.model_id
            and template.offer.market_context is not None
            and template.offer.market_context.distance_band == target.band
            and snapshot.bindings.get(template.template_id) in offer_ids
        )

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

    @staticmethod
    def _log(
        snapshot: StockSnapshot,
        target: StockTarget | None,
        started: float,
        provider_ms: float,
    ) -> None:
        """Record bounded phase timings without account identities."""
        durations = {
            name: round(value, 2) for name, value in snapshot.phase_durations
        }
        durations["provider"] = round(provider_ms, 2)
        durations["round"] = round((perf_counter() - started) * 1000, 2)
        LOGGER.info(
            "Player market stock preparation progress",
            extra={
                "event": "market.stock_preparation_progress",
                "data": {
                    "priority": target.priority + 1 if target else None,
                    "city": (
                        target.demand.vehicle.city_uid if target else None
                    ),
                    "model": (
                        target.demand.vehicle.model_id if target else None
                    ),
                    "distance_band": target.band if target else None,
                    "candidate_count": len(snapshot.candidates),
                    "relation_count": len(
                        required_relations(snapshot.candidates)
                    ),
                    "durations_ms": durations,
                },
            },
        )

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
