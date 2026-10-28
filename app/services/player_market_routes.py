"""Project player offer bindings and shared routes in one read snapshot."""

from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.market import MarketVehicle
from app.domain.readiness_ports import OfferRouteStore
from app.domain.routing_readiness import RouteReference
from app.services.routing_readiness import RoutingReadinessService

RoutePair = tuple[str, str]


@dataclass(frozen=True, slots=True)
class PlayerMarketRouteSnapshot:
    """Hold all route facts required by one market projection."""

    offer_references: dict[str, RouteReference]
    route_references: dict[RoutePair, RouteReference]


@dataclass(slots=True)
class PlayerMarketRouteService:
    """Load and apply player-bound route facts without per-offer reads."""

    readiness: RoutingReadinessService
    references: OfferRouteStore

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

    def retained(
        self,
        offer: ContractOffer,
        snapshot: PlayerMarketRouteSnapshot,
    ) -> bool:
        """Require the offer's exact bound delivery revision."""
        delivery = (
            offer.origin.facility_uid,
            offer.destination.facility_uid,
        )
        return snapshot.offer_references.get(
            offer.id
        ) == snapshot.route_references.get(delivery)

    def eligible(
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
