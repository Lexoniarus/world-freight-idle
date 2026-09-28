"""Compact runtime facts and separate immutable geometry read contracts."""

from dataclasses import dataclass
from math import isclose
from typing import Protocol

from app.domain.contracts import HistoricalContractSnapshot
from app.domain.economics import CostBreakdown
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.journeys import JourneyPlan
from app.domain.market_preparation import PreparationStatus
from app.domain.read_ports import SharedTransport
from app.domain.validation import (
    require_finite,
    require_identity,
    require_integer,
)
from app.domain.world import FacilityLocationSnapshot


@dataclass(frozen=True, slots=True)
class RuntimeTransport:
    """Saved private transport facts without constructing a road geometry."""

    id: str
    vehicle_id: str
    contract: HistoricalContractSnapshot
    origin: FacilityLocationSnapshot
    destination: FacilityLocationSnapshot
    start: FacilityLocationSnapshot
    journey: JourneyPlan
    distance_km: float
    routing_duration_seconds: float
    provider: str
    approach_distance_km: float
    departed_at: float
    arrives_at: float
    payout_eur: int
    operating_cost_eur: int
    cost_breakdown: CostBreakdown | None

    def __post_init__(self) -> None:
        """Reject inconsistent scalar facts without hydrating coordinates."""
        for value in (self.id, self.vehicle_id, self.provider):
            require_identity(value, "Runtime transport identity")
        for measurement in (
            self.distance_km,
            self.routing_duration_seconds,
            self.departed_at,
            self.arrives_at,
            self.approach_distance_km,
        ):
            require_finite(measurement, "Runtime transport value")
        require_integer(self.payout_eur, "Payout")
        require_integer(self.operating_cost_eur, "Operating cost")
        if (
            self.distance_km != self.journey.distance_km
            or not isclose(
                self.arrives_at - self.departed_at,
                self.journey.duration_seconds,
                abs_tol=1e-6,
            )
            or self.origin != self.contract.origin
            or self.destination != self.contract.destination
            or self.approach_distance_km > self.distance_km
            or self.routing_duration_seconds <= 0
            or (
                self.start.facility_uid != self.origin.facility_uid
                and self.approach_distance_km == 0
            )
            or (
                self.cost_breakdown is not None
                and self.cost_breakdown.total_cost_eur
                != self.operating_cost_eur
            )
        ):
            raise ValueError("Runtime transport facts differ.")


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    """One consistent owner snapshot independent of map downloads."""

    player: PlayerState
    vehicles: tuple[OwnedVehicle, ...]
    transports: tuple[RuntimeTransport, ...]


@dataclass(frozen=True, slots=True)
class RuntimeView:
    """Attach server timing and durable preparation state to a snapshot."""

    state: RuntimeSnapshot
    server_time: float
    time_scale: float
    preparation: PreparationStatus | None


@dataclass(frozen=True, slots=True)
class GeometrySpan:
    """Describe a leg by indices into the sole coordinate array."""

    purpose: str
    start_index: int
    end_index: int
    start_km: float
    end_km: float
    routing_duration_seconds: float


@dataclass(frozen=True, slots=True)
class TransportGeometry:
    """Keep exact historic coordinates separate from mutable presentation."""

    coordinates: tuple[tuple[float, float], ...]
    legs: tuple[GeometrySpan, ...]


class RuntimeReader(Protocol):
    """Read private summaries and authorized immutable map resources."""

    def read(self, user_id: str) -> RuntimeSnapshot: ...

    def traffic(self, now: float) -> tuple[SharedTransport, ...]: ...

    def visible(
        self, owner_id: str, trip_id: str, viewer_id: str, now: float
    ) -> bool: ...

    def geometry(self, owner_id: str, trip_id: str) -> TransportGeometry: ...
