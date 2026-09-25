"""Immutable road routes and the ordered pickup approach contract."""

from dataclasses import dataclass
from typing import Literal

from app.domain.validation import require_finite, require_identity
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
class RouteLeg:
    """Public movement geometry with authoritative distance boundaries."""

    purpose: Literal["approach", "delivery"]
    start_km: float
    end_km: float
    routing_duration_seconds: float
    coordinates: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class DispatchRoutePlan:
    """Separate actual departure, pickup and delivery road measurements."""

    start: FacilityLocationSnapshot
    pickup: FacilityLocationSnapshot
    destination: FacilityLocationSnapshot
    delivery: RouteSnapshot
    approach: RouteSnapshot | None = None

    def __post_init__(self) -> None:
        """Require routable endpoints and an explicit nonlocal approach."""
        if any(
            p.coordinates is None
            for p in (self.start, self.pickup, self.destination)
        ):
            raise ValueError("Fahrtplan enthält keine routbaren Koordinaten.")
        if self.start.city.city_uid != self.pickup.city.city_uid:
            raise ValueError("Fahrzeug steht nicht in der Abholstadt.")
        if self.approach is None and (
            self.start.facility_uid != self.pickup.facility_uid
            and self.start.coordinates != self.pickup.coordinates
        ):
            raise ValueError("Distinct pickup requires an approach route.")

    @property
    def total_route(self) -> RouteSnapshot:
        """Compose total measurements for existing route consumers."""
        if self.approach is None:
            return self.delivery
        coordinates = (
            self.approach.coordinates
            + self.delivery.coordinates[
                int(
                    self.approach.coordinates[-1]
                    == self.delivery.coordinates[0]
                ) :
            ]
        )
        return RouteSnapshot(
            coordinates,
            self.approach.distance_km + self.delivery.distance_km,
            self.approach.duration_seconds + self.delivery.duration_seconds,
            self.delivery.provider,
        )

    @property
    def legs(self) -> tuple[RouteLeg, ...]:
        """Expose only geometry and movement boundaries, never economics."""
        distance = self.approach.distance_km if self.approach else 0.0
        delivery = RouteLeg(
            "delivery",
            distance,
            distance + self.delivery.distance_km,
            self.delivery.duration_seconds,
            self.delivery.coordinates,
        )
        if self.approach is None:
            return (delivery,)
        return (
            RouteLeg(
                "approach",
                0.0,
                distance,
                self.approach.duration_seconds,
                self.approach.coordinates,
            ),
            delivery,
        )
