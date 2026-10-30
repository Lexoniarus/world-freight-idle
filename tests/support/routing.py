"""Shared routing doubles and factories for isolated tests."""

from app.domain.geography import Address, City, Coordinates, Country
from app.domain.routing_anchors import (
    LocateResult,
    RoutingAnchor,
    RoutingAnchorStatus,
    RoutingCandidate,
)
from app.domain.transports import RouteSnapshot
from app.domain.world import Facility


class MemoryAnchorStore:
    """Store routing anchors in memory behind the production port."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], RoutingAnchor] = {}

    def get(
        self,
        facility_uid: str,
        routing_profile: str,
    ) -> RoutingAnchor | None:
        """Return one saved anchor."""
        return self.items.get((facility_uid, routing_profile))

    def get_many(
        self,
        facility_uids: tuple[str, ...],
        routing_profile: str,
    ) -> dict[str, RoutingAnchor]:
        """Return saved anchors for the requested facilities."""
        return {
            facility_uid: anchor
            for facility_uid in facility_uids
            if (anchor := self.items.get((facility_uid, routing_profile)))
            is not None
        }

    def put(self, anchor: RoutingAnchor) -> None:
        """Save one anchor."""
        self.items[(anchor.facility_uid, anchor.routing_profile)] = anchor

    def put_leased(
        self, anchor: RoutingAnchor, owner: str, now: float
    ) -> bool:
        """Save one anchor for the test lease owner."""
        self.put(anchor)
        return True


class FakeLocator:
    """Return configured provider locate results in order."""

    def __init__(self, results: list[LocateResult]) -> None:
        self.results = results
        self.calls: list[Coordinates] = []

    async def locate(self, coordinates: Coordinates) -> LocateResult:
        """Record and resolve one locate request."""
        self.calls.append(coordinates)
        return self.results.pop(0)


class FakeGeocoder:
    """Return one configured geocoding result or failure."""

    def __init__(
        self,
        result: tuple[float, float, str] = (52.5, 13.4, "resolved"),
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    async def geocode(self, address: str) -> tuple[float, float, str]:
        """Record and resolve one geocoding request."""
        self.calls.append(address)
        if self.error is not None:
            raise self.error
        return self.result


class FakeRouter:
    """Return one deterministic truck route without provider access."""

    async def route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteSnapshot:
        """Connect the requested endpoints with stable route metrics."""
        return RouteSnapshot(
            distance_km=400.0,
            duration_seconds=14400.0,
            coordinates=(
                (origin_lon, origin_lat),
                (destination_lon, destination_lat),
            ),
            provider="fake-router",
        )


class FakeRoutingAnchorResolver:
    """Expose each catalogue coordinate as one local routing candidate."""

    max_snap_distance_m = 1000.0

    async def resolve(
        self, facility: Facility, *, force: bool = False
    ) -> tuple[RoutingCandidate, ...]:
        """Return a candidate only when the facility has coordinates."""
        if facility.coordinates is None:
            return ()
        return (
            RoutingCandidate(
                facility.coordinates,
                0.0,
                "fake-anchor",
                None,
            ),
        )


def facility(
    coordinates: Coordinates | None = Coordinates(52.52, 13.405),
) -> Facility:
    """Build one stable facility for routing tests."""
    country = Country("DE", "Germany")
    city = City(
        "8b631e25-6e3b-4d20-b1ea-2f3c4de8e7fb",
        "Berlin",
        country,
    )
    return Facility(
        facility_uid="facility-1",
        company=None,
        label="Depot",
        facility_type="depot",
        address=Address(city, "Teststrasse", "1", "10115"),
        coordinates=coordinates,
        geocoding_status="estimated_for_simulation",
        sources=(),
        coordinate_evidence=(),
        nhm_profiles=(),
        catalogue_version="test",
    )


def located(
    *,
    accepted: bool = True,
    distance: float | None = 12.0,
    status: RoutingAnchorStatus = "validated",
    coordinates: Coordinates | None = Coordinates(52.5201, 13.4051),
) -> LocateResult:
    """Build one stable locate response."""
    return LocateResult(
        accepted=accepted,
        coordinates=coordinates if accepted else None,
        snap_distance_m=distance,
        provider="Valhalla",
        provider_revision="graph-1",
        status=status,
        candidates=(
            RoutingCandidate(
                coordinates, distance or 0, "Valhalla", "graph-1"
            ),
        )
        if accepted and coordinates
        else (),
    )
