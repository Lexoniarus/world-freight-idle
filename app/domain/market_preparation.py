"""Persistent player preparation contracts, separate from global routes."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from app.domain.market import CompatibleVehicle, MarketCandidate, MarketVehicle
from app.domain.routing_readiness import RelationStatus, RouteReference


@dataclass(frozen=True, slots=True)
class RelationDemandState:
    """Describe current evidence and expected routing inputs for demand."""

    origin_uid: str
    destination_uid: str
    expected_fingerprint: str
    status: RelationStatus | None
    reference: RouteReference | None


@dataclass(frozen=True, slots=True)
class PreparationStatus:
    """Public coverage progress without raw provider diagnostics."""

    preparation_id: str
    generation: str
    status: str
    next_retry_at: float | None


class PreparationStore(Protocol):
    """Persist fair, resumable player demand on the relational runtime."""

    def request(self, user_id: str, generation: str, now: float) -> None: ...

    def status(self, user_id: str) -> PreparationStatus | None: ...

    def next_player(self, now: float) -> str | None: ...

    def finish(
        self,
        user_id: str,
        generation: str,
        status: str,
        retry_at: float | None,
        now: float,
    ) -> None: ...


def preparation_generation(
    fleet: tuple[MarketVehicle, ...],
    candidates: tuple[MarketCandidate, ...],
    references: tuple[RelationDemandState, ...],
) -> str:
    """Fingerprint relevant demand without copying entire facility trees."""
    facts = tuple(
        (
            c.trade.origin.facility_uid,
            c.trade.destination.facility_uid,
            c.trade.cargo.nhm_row_id,
            c.profile,
            c.weight,
        )
        for c in candidates
    )
    return sha256(repr((fleet, facts, references)).encode()).hexdigest()


def required_relations(
    candidates: tuple[MarketCandidate, ...],
) -> tuple[tuple[str, str], ...]:
    """Prioritize deduplicated approaches before changing delivery choices."""
    pairs: dict[tuple[str, str], None] = {}
    for candidate in candidates:
        origin = candidate.trade.origin.facility_uid
        for compatible in candidate.vehicles:
            start = compatible.vehicle.facility_uid
            if start != origin:
                pairs[start, origin] = None
    for candidate in candidates:
        pairs[
            candidate.trade.origin.facility_uid,
            candidate.trade.destination.facility_uid,
        ] = None
    return tuple(pairs)


@dataclass(frozen=True, slots=True)
class VehicleReadyCandidate:
    """Bind a delivery revision to individually ready approach contexts."""

    candidate: MarketCandidate
    delivery: RouteReference
    vehicles: tuple[CompatibleVehicle, ...]
