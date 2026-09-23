"""Transport lifecycle independent of persistence, clocks and providers."""

from dataclasses import dataclass, replace
from math import isclose
from typing import Literal

from app.domain.contracts import HistoricalContractSnapshot
from app.domain.journeys import JourneyPlan, JourneyProgress
from app.domain.validation import (
    require_finite,
    require_identity,
    require_integer,
)
from app.domain.world import FacilityLocationSnapshot


@dataclass(frozen=True, slots=True)
class RouteSnapshot:
    """Immutable routed geometry and provider measurements."""

    coordinates: tuple[tuple[float, float], ...]
    distance_km: float
    duration_seconds: float
    provider: str

    def __post_init__(self) -> None:
        """Reject malformed geometry and invalid provider measurements."""
        require_finite(self.distance_km, "Distance", 0.000001)
        require_finite(self.duration_seconds, "Duration", 0.000001)
        require_identity(self.provider, "Route provider")
        if not isinstance(self.coordinates, tuple) or any(
            not isinstance(point, tuple) for point in self.coordinates
        ):
            raise ValueError("Route coordinates must be immutable tuples.")
        if len(self.coordinates) < 2:
            raise ValueError("A route requires at least two coordinates.")
        for longitude, latitude in self.coordinates:
            require_finite(longitude, "Longitude", -180)
            require_finite(latitude, "Latitude", -90)
            if longitude > 180 or latitude > 90:
                raise ValueError("Route coordinate outside WGS84.")


@dataclass(frozen=True, slots=True)
class ActiveTransport:
    """A historical dispatch with an explicit one-way settlement lifecycle."""

    id: str
    vehicle_id: str
    contract: HistoricalContractSnapshot
    origin: FacilityLocationSnapshot
    destination: FacilityLocationSnapshot
    route: RouteSnapshot
    departed_at: float
    arrives_at: float
    payout_eur: int
    operating_cost_eur: int
    journey: JourneyPlan
    status: Literal["active", "settled"] = "active"
    settled_at: float | None = None

    def __post_init__(self) -> None:
        """Protect identities, immutable economics and timeline ordering."""
        require_identity(self.id, "Transport ID")
        require_identity(self.vehicle_id, "Vehicle ID")
        require_finite(self.departed_at, "Departure")
        require_finite(self.arrives_at, "Arrival")
        require_integer(self.payout_eur, "Payout")
        require_integer(self.operating_cost_eur, "Operating cost")
        if self.arrives_at <= self.departed_at:
            raise ValueError("Arrival must follow departure.")
        if (
            self.origin.facility_uid != self.contract.origin.facility_uid
            or self.destination.facility_uid
            != self.contract.destination.facility_uid
        ):
            raise ValueError("Transport endpoints differ from its contract.")
        if self.journey.distance_km != self.route.distance_km or not isclose(
            self.journey.duration_seconds,
            self.arrives_at - self.departed_at,
            rel_tol=1e-9,
            abs_tol=1e-6,
        ):
            raise ValueError("Transport and journey timeline differ.")
        if self.status == "active":
            if self.settled_at is not None:
                raise ValueError("Active transport cannot be settled.")
        elif self.status == "settled":
            if self.settled_at is None:
                raise ValueError("Settlement requires a timestamp.")
            require_finite(self.settled_at, "Settlement", self.arrives_at)
        else:
            raise ValueError("Invalid transport status.")

    def is_due(self, now: float) -> bool:
        """Identify pending settlement using caller-supplied server time."""
        require_finite(now, "Current time")
        return self.status == "active" and now >= self.arrives_at

    def settle(self, now: float) -> "ActiveTransport":
        """Return the settled state; reject premature or repeated payment."""
        if not self.is_due(now):
            raise ValueError("Transport is not due for settlement.")
        return replace(self, status="settled", settled_at=now)

    def progress_at(self, now: float) -> JourneyProgress:
        """Evaluate the historical journey at caller-supplied server time."""
        require_finite(now, "Current time")
        return self.journey.progress_at(now - self.departed_at)
