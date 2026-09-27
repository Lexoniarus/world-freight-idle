"""Plan player routing demand separately from worker scheduling."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.market import MarketCandidate, MarketVehicle
from app.domain.state_ports import GameStateRepository
from app.services.market_candidates import MarketCandidateService
from app.services.market_coverage import MarketCoverageService
from app.services.market_preparation import MarketPreparationService
from app.services.market_scope import MarketScopeResolver
from app.services.vehicle_coverage import VehicleCoverageService


@dataclass(frozen=True, slots=True)
class PreparationBatchPlan:
    """Capture one generation's bounded demand and coverage evidence."""

    generation: str
    needed: tuple[MarketCandidate, ...]
    fleet: tuple[MarketVehicle, ...]
    exhausted: bool
    structural_count: int
    relation_states: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class PreparationBatchResult:
    """Return scheduling facts without exposing market internals."""

    generation: str
    status: str
    retry_at: float | None
    structural_count: int
    relation_states: tuple[tuple[str, int], ...]


class MarketPreparationBatchService:
    """Own coverage planning and revalidation around provider work."""

    def __init__(
        self,
        repository: GameStateRepository,
        candidates: MarketCandidateService,
        coverage: MarketCoverageService,
        scope: MarketScopeResolver,
        preparation: MarketPreparationService,
        refresh: Callable[[], list[ContractOffer]],
        vehicle_coverage: VehicleCoverageService,
    ) -> None:
        """Inject state reads, pure market steps and transactional refresh."""
        self.repository = repository
        self.candidates = candidates
        self.coverage = coverage
        self.scope = scope
        self.preparation = preparation
        self.refresh = refresh
        self.vehicle_coverage = vehicle_coverage

    def plan(self) -> PreparationBatchPlan:
        """Read refreshed publication and determine still-needed relations."""
        with self.preparation.transactions.transaction():
            return self._plan_in_transaction()

    def _plan_in_transaction(self) -> PreparationBatchPlan:
        """Assemble cached demand within the active local transaction."""
        offers = tuple(self.refresh())
        status = self.preparation.jobs.status(self.preparation.user_id)
        assert status is not None
        owned = self.repository.list_vehicles()
        fleet = self.candidates.resolve_fleet(owned)
        cities = self.scope.resolve(owned)
        candidates = self.candidates.build(cities, fleet)
        states = {
            pair: self.preparation.readiness.current(*pair)
            for pair in dict.fromkeys(
                (c.trade.origin.facility_uid, c.trade.destination.facility_uid)
                for c in candidates
            )
        }
        usable = self.preparation.preparable_candidates(candidates)
        ready = self.preparation.ready_candidates(candidates)
        vehicles = self.vehicle_coverage
        coverage = vehicles.extend(
            self.coverage.plan(cities, usable, offers),
            usable,
            offers,
            fleet,
            ready,
        )
        published = {
            (o.origin.facility_uid, o.destination.facility_uid) for o in offers
        }
        needed = tuple(
            dict.fromkeys(
                (
                    *coverage.selected,
                    *(
                        c
                        for c in usable
                        if (
                            c.trade.origin.facility_uid,
                            c.trade.destination.facility_uid,
                        )
                        in published
                    ),
                )
            )
        )
        unmet = vehicles.extend(
            self.coverage.plan(cities, candidates, offers),
            candidates,
            offers,
            fleet,
            ready,
        )
        return PreparationBatchPlan(
            status.generation,
            needed,
            fleet,
            not coverage.selected and bool(unmet.selected),
            len(candidates),
            tuple(
                sorted(
                    Counter(
                        relation.status if relation else "unchecked_or_stale"
                        for relation in states.values()
                    ).items()
                )
            ),
        )

    async def process(self) -> PreparationBatchResult:
        """Prepare outside transactions and evaluate fresh publication."""
        plan = self.plan()
        complete, retry_at = await self.preparation.prepare_batch(
            plan.needed, plan.fleet
        )
        current = self.plan()
        outcome = "partial"
        if complete and current.generation == plan.generation:
            if current.exhausted:
                outcome = "exhausted"
            elif not current.needed or self._ready(current):
                outcome = "ready"
        return PreparationBatchResult(
            plan.generation,
            outcome,
            retry_at,
            current.structural_count,
            current.relation_states,
        )

    def _ready(self, plan: PreparationBatchPlan) -> bool:
        """Require every planned delivery and approach to be ready."""
        from app.domain.market_preparation import required_relations

        return all(
            self.preparation.readiness.ready(*pair) is not None
            for pair in required_relations(plan.needed)
        )
