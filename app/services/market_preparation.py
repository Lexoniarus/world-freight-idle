"""Separate structural candidates from publication-ready market work."""

from collections.abc import Callable

from app.domain.contracts import ContractOffer
from app.domain.market import MarketCandidate, MarketVehicle
from app.domain.market_preparation import (
    PreparationStore,
    RelationDemandState,
    VehicleReadyCandidate,
    preparation_generation,
    required_relations,
)
from app.domain.market_stock import MarketStockStore, StockPolicy
from app.domain.readiness_ports import OfferRouteStore
from app.domain.routing_readiness import RouteReference
from app.domain.state_ports import TransactionBoundary
from app.services.routing_readiness import RoutingReadinessService
from app.services.vehicle_coverage import restrict_candidate


class MarketPreparationService:
    """Bind player demand and offer references to global readiness."""

    def __init__(
        self,
        user_id: str,
        readiness: RoutingReadinessService,
        references: OfferRouteStore,
        jobs: PreparationStore,
        clock: Callable[[], float],
        transactions: TransactionBoundary,
        stock: MarketStockStore | None = None,
        policy: StockPolicy = StockPolicy(),
    ) -> None:
        """Inject global readiness and player-scoped reference storage."""
        self.user_id = user_id
        self.readiness = readiness
        self.references = references
        self.jobs = jobs
        self.clock = clock
        self.transactions = transactions
        self.stock = stock
        self.policy = policy

    def prepare_publication(
        self,
        candidates: tuple[MarketCandidate, ...],
        fleet: tuple[MarketVehicle, ...],
    ) -> tuple[MarketCandidate, ...]:
        """Enqueue demand and expose vehicle-ready structural candidates."""
        pairs = required_relations(candidates)
        states = tuple(self.demand_state(*pair) for pair in pairs)
        generation = preparation_generation(fleet, candidates, states)
        with self.transactions.transaction():
            self.jobs.request(self.user_id, generation, self.clock())
        return self._ready_candidates(candidates, states)

    def request(self, *, changed: bool = False) -> None:
        """Schedule durable demand without building a candidate pool."""
        if changed:
            with self.transactions.transaction():
                self.jobs.invalidate(self.user_id, self.clock())
        else:
            self.jobs.ensure(self.user_id, self.clock())

    def ready_candidates(
        self,
        candidates: tuple[MarketCandidate, ...],
    ) -> tuple[MarketCandidate, ...]:
        """Expose only candidates with a usable delivery and vehicle start."""
        with self.readiness.reading():
            states = tuple(
                self.demand_state(*pair)
                for pair in required_relations(candidates)
            )
            return self._ready_candidates(candidates, states)

    def _ready_candidates(
        self,
        candidates: tuple[MarketCandidate, ...],
        states: tuple[RelationDemandState, ...],
    ) -> tuple[MarketCandidate, ...]:
        """Project one consistent local evidence set into ready contexts."""
        references = {
            (s.origin_uid, s.destination_uid): s.reference
            for s in states
            if s.status == "ready"
        }
        return tuple(
            restrict_candidate(context.candidate, context.vehicles)
            for candidate in candidates
            if (context := self.ready_context(candidate, references))
            is not None
        )

    def ready_context(
        self,
        candidate: MarketCandidate,
        references: dict[tuple[str, str], RouteReference | None],
    ) -> VehicleReadyCandidate | None:
        """Map delivery and approach evidence to immutable vehicle context."""
        origin = candidate.trade.origin.facility_uid
        delivery = references.get(
            (origin, candidate.trade.destination.facility_uid)
        )
        vehicles = tuple(
            v
            for v in candidate.vehicles
            if v.vehicle.facility_uid == origin
            or references.get((v.vehicle.facility_uid, origin)) is not None
        )
        if delivery is None or not vehicles:
            return None
        return VehicleReadyCandidate(candidate, delivery, vehicles)

    def preparable_candidates(
        self,
        candidates: tuple[MarketCandidate, ...],
    ) -> tuple[MarketCandidate, ...]:
        """Skip deterministic delivery or approach failures during planning."""
        with self.readiness.reading():
            states = {
                pair: self.readiness.current(*pair)
                for pair in required_relations(candidates)
            }
            result = []
            for candidate in candidates:
                origin = candidate.trade.origin.facility_uid
                relation = states[
                    origin, candidate.trade.destination.facility_uid
                ]
                if relation and relation.status == "deterministic_failure":
                    continue
                vehicles = tuple(
                    v
                    for v in candidate.vehicles
                    if v.vehicle.facility_uid == origin
                    or (approach := states[v.vehicle.facility_uid, origin])
                    is None
                    or approach.status != "deterministic_failure"
                )
                if vehicles:
                    result.append(restrict_candidate(candidate, vehicles))
            return tuple(result)

    def demand_state(
        self, origin: str, destination: str
    ) -> RelationDemandState:
        """Read stable routing facts including stale negative evidence."""
        relation = self.readiness.current(origin, destination)
        return RelationDemandState(
            origin,
            destination,
            self.readiness.fingerprint(origin, destination),
            relation.status if relation else None,
            relation.reference if relation else None,
        )

    def retained(self, offer: ContractOffer) -> bool:
        """Require the exact persisted revision before retaining an offer."""
        reference = self.references.get(offer.id)
        return reference is not None and reference == self.readiness.ready(
            offer.origin.facility_uid, offer.destination.facility_uid
        )

    def eligible(
        self,
        offer: ContractOffer,
        fleet: tuple[MarketVehicle, ...],
        structural_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Add actual-start approach readiness to shared vehicle rules."""
        return tuple(
            vehicle.vehicle_id
            for vehicle in fleet
            if vehicle.vehicle_id in structural_ids
            and (
                vehicle.facility_uid == offer.origin.facility_uid
                or self.readiness.ready(
                    vehicle.facility_uid, offer.origin.facility_uid
                )
                is not None
            )
        )

    def bind(self, offers: tuple[ContractOffer, ...]) -> None:
        """Own atomic binding, joining a surrounding market transaction."""
        with self.transactions.transaction():
            self._bind_in_transaction(offers)

    def _bind_in_transaction(self, offers: tuple[ContractOffer, ...]) -> None:
        """Validate and replace references inside the active transaction."""
        bindings = []
        for offer in offers:
            reference = self.readiness.ready(
                offer.origin.facility_uid, offer.destination.facility_uid
            )
            if reference is None:
                raise ValueError(
                    "Market publication requires route readiness."
                )
            bindings.append((offer.id, reference))
        self.references.replace(tuple(bindings))

    async def prepare_batch(
        self,
        candidates: tuple[MarketCandidate, ...],
        fleet: tuple[MarketVehicle, ...],
        limit: int = 4,
    ) -> tuple[bool, float | None]:
        """Prepare a bounded batch; provider adapters own request pacing."""
        pairs = required_relations(candidates)
        count = 0
        waiting = False
        retry_at = None
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
                return False, self.clock()
            count += 1
            result = await self.readiness.prepare(origin, destination)
            if result is None or result.status == "transient_failure":
                waiting = True
                next_try = (
                    result.retry_at if result else None
                ) or self.clock() + 1
                retry_at = min(retry_at or next_try, next_try)
        return not waiting, retry_at
