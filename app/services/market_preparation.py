"""Separate structural candidates from publication-ready market work."""

from collections.abc import Callable

from app.domain.contracts import ContractOffer
from app.domain.market import MarketCandidate, MarketVehicle
from app.domain.market_preparation import (
    PreparationStore,
    preparation_generation,
    required_relations,
)
from app.domain.readiness_ports import OfferRouteStore
from app.services.routing_readiness import RoutingReadinessService


class MarketPreparationService:
    """Bind player demand and offer references to global readiness."""

    def __init__(
        self,
        user_id: str,
        readiness: RoutingReadinessService,
        references: OfferRouteStore,
        jobs: PreparationStore,
        clock: Callable[[], float],
    ) -> None:
        """Inject global readiness and player-scoped reference storage."""
        self.user_id = user_id
        self.readiness = readiness
        self.references = references
        self.jobs = jobs
        self.clock = clock

    def prepare_publication(
        self,
        candidates: tuple[MarketCandidate, ...],
        fleet: tuple[MarketVehicle, ...],
    ) -> tuple[MarketCandidate, ...]:
        """Enqueue demand and expose delivery-ready structural candidates."""
        pairs = required_relations(candidates)
        references = {pair: self.readiness.ready(*pair) for pair in pairs}
        generation = preparation_generation(
            fleet, candidates, tuple(references.items())
        )
        self.jobs.request(self.user_id, generation, self.clock())
        return tuple(
            candidate
            for candidate in candidates
            if references[
                candidate.trade.origin.facility_uid,
                candidate.trade.destination.facility_uid,
            ]
            is not None
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
        """Write exact route references within the caller's market UoW."""
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
