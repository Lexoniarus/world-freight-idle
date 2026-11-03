"""Own player offer bindings and reusable shared route readiness."""

from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.market import MarketCandidate, MarketVehicle
from app.domain.market_preparation import (
    RelationDemandState,
    VehicleReadyCandidate,
    required_relations,
)
from app.domain.readiness_ports import OfferRouteStore
from app.domain.routing_readiness import RouteReference
from app.domain.state_ports import TransactionBoundary
from app.services.market.vehicle_coverage import restrict_candidate
from app.services.routing.evidence import RoutingEvidenceReader

RoutePair = tuple[str, str]


@dataclass(frozen=True, slots=True)
class PlayerMarketRouteSnapshot:
    """Hold all route facts required by one market projection."""

    offer_references: dict[str, RouteReference]
    route_references: dict[RoutePair, RouteReference]


@dataclass(slots=True)
class PlayerMarketRouteService:
    """Load and apply player-bound route facts without per-offer reads."""

    readiness: RoutingEvidenceReader
    references: OfferRouteStore
    transactions: TransactionBoundary

    def read(
        self,
        offers: tuple[ContractOffer, ...],
        fleet: tuple[MarketVehicle, ...],
    ) -> PlayerMarketRouteSnapshot:
        """Read offer bindings and all required relation revisions once."""
        pairs = self._required_pairs(offers, fleet)
        with self.readiness.reading(pairs):
            route_references = {
                pair: reference
                for pair in pairs
                if (reference := self.readiness.ready(*pair)) is not None
            }
        offer_references = self.references.get_many(
            tuple(offer.id for offer in offers)
        )
        return PlayerMarketRouteSnapshot(
            offer_references,
            route_references,
        )

    def matches_snapshot(
        self,
        offer: ContractOffer,
        snapshot: PlayerMarketRouteSnapshot,
    ) -> bool:
        """Require the offer's exact bound delivery revision."""
        delivery = (
            offer.origin.facility_uid,
            offer.destination.facility_uid,
        )
        bound = snapshot.offer_references.get(offer.id)
        return bound is not None and bound == snapshot.route_references.get(
            delivery
        )

    def eligible_from_snapshot(
        self,
        offer: ContractOffer,
        fleet: tuple[MarketVehicle, ...],
        structural_ids: tuple[str, ...],
        snapshot: PlayerMarketRouteSnapshot,
    ) -> tuple[str, ...]:
        """Apply cached approach readiness to structural eligibility."""
        return tuple(
            vehicle.vehicle_id
            for vehicle in fleet
            if vehicle.vehicle_id in structural_ids
            and (
                vehicle.facility_uid == offer.origin.facility_uid
                or (
                    vehicle.facility_uid,
                    offer.origin.facility_uid,
                )
                in snapshot.route_references
            )
        )

    def retained_current(self, offer: ContractOffer) -> bool:
        """Require the exact persisted delivery revision for one offer."""
        reference = self.references.get(offer.id)
        return reference is not None and reference == self.readiness.ready(
            offer.origin.facility_uid,
            offer.destination.facility_uid,
        )

    def ready_candidates(
        self,
        candidates: tuple[MarketCandidate, ...],
    ) -> tuple[MarketCandidate, ...]:
        """Expose candidates with ready delivery and vehicle approaches."""
        pairs = required_relations(candidates)
        with self.readiness.reading(pairs):
            states = tuple(self.demand_state(*pair) for pair in pairs)
            return self._ready_candidates(candidates, states)

    def _ready_candidates(
        self,
        candidates: tuple[MarketCandidate, ...],
        states: tuple[RelationDemandState, ...],
    ) -> tuple[MarketCandidate, ...]:
        """Project one consistent evidence set into ready contexts."""
        references = {
            (state.origin_uid, state.destination_uid): state.reference
            for state in states
            if state.status == "ready"
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
        references: dict[RoutePair, RouteReference | None],
    ) -> VehicleReadyCandidate | None:
        """Map delivery and approach evidence to immutable vehicle context."""
        origin = candidate.trade.origin.facility_uid
        delivery = references.get(
            (origin, candidate.trade.destination.facility_uid)
        )
        vehicles = tuple(
            item
            for item in candidate.vehicles
            if item.vehicle.facility_uid == origin
            or references.get((item.vehicle.facility_uid, origin)) is not None
        )
        if delivery is None or not vehicles:
            return None
        return VehicleReadyCandidate(candidate, delivery, vehicles)

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

    def bind(self, offers: tuple[ContractOffer, ...]) -> None:
        """Own atomic offer binding within a surrounding transaction."""
        with self.transactions.transaction():
            self.bind_in_transaction(offers)

    def bind_in_transaction(self, offers: tuple[ContractOffer, ...]) -> None:
        """Validate and replace references inside the active transaction."""
        bindings = []
        for offer in offers:
            reference = self.readiness.ready(
                offer.origin.facility_uid,
                offer.destination.facility_uid,
            )
            if reference is None:
                raise ValueError(
                    "Market publication requires route readiness."
                )
            bindings.append((offer.id, reference))
        self.references.replace(tuple(bindings))

    def _required_pairs(
        self,
        offers: tuple[ContractOffer, ...],
        fleet: tuple[MarketVehicle, ...],
    ) -> tuple[RoutePair, ...]:
        """Deduplicate delivery and vehicle-approach relations."""
        pairs: dict[RoutePair, None] = {}
        for offer in offers:
            origin = offer.origin.facility_uid
            pairs[origin, offer.destination.facility_uid] = None
            for vehicle in fleet:
                if vehicle.facility_uid != origin:
                    pairs[vehicle.facility_uid, origin] = None
        return tuple(pairs)
