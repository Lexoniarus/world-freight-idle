"""Shared routing doubles and factories for isolated tests."""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from hashlib import sha256

from app.domain.geography import Address, City, Coordinates, Country
from app.domain.ports import WorldCatalogue
from app.domain.routing_anchors import (
    LocateResult,
    RoutingAnchor,
    RoutingAnchorStatus,
    RoutingCandidate,
)
from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingRelation,
    relation_identity,
)
from app.domain.transports import RouteSnapshot
from app.domain.world import Facility
from app.domain.world_scopes import WorldScope


class FixtureRoutingReadiness:
    """Expose deterministic prepared evidence without provider work."""

    def __init__(
        self,
        world: WorldCatalogue,
        clock: Callable[[], float],
    ) -> None:
        """Index the injected immutable catalogue for local route reads."""
        self.world = world
        self.clock = clock

    @contextmanager
    def reading(
        self,
        pairs: Iterable[tuple[str, str]] = (),
    ) -> Iterator[None]:
        """Match the production evidence read boundary without I/O."""
        del pairs
        yield

    def fingerprint(self, origin: str, destination: str) -> str:
        """Return a stable test-only evidence fingerprint."""
        return sha256(f"fixture:{origin}:{destination}".encode()).hexdigest()

    def ready(self, origin: str, destination: str) -> RouteReference:
        """Return the stable prepared reference for one directed relation."""
        return RouteReference(
            relation_identity(origin, destination),
            self.fingerprint(origin, destination),
        )

    def current(self, origin: str, destination: str) -> RoutingRelation:
        """Return current ready evidence for worker projections."""
        return RoutingRelation(
            self.ready(origin, destination),
            origin,
            destination,
            self.fingerprint(origin, destination),
            "ready",
            None,
            None,
            self.clock(),
        )

    def load(self, origin: str, destination: str) -> RoutePayload:
        """Build stable local metrics from catalogue coordinates."""
        scope = WorldScope(self.world.read())
        start = scope.facility(origin).coordinates
        end = scope.facility(destination).coordinates
        if start is None or end is None:
            raise ValueError("Fixture route requires catalogue coordinates.")
        return RoutePayload(
            (
                (start.longitude, start.latitude),
                (end.longitude, end.latitude),
            ),
            400.0,
            14400.0,
            "fixture-router",
        )


class MemoryOfferRouteStore:
    """Keep fixture offer bindings behind the production store port."""

    def __init__(self) -> None:
        """Start with no published offer references."""
        self.items: dict[str, RouteReference] = {}

    def get(self, offer_id: str) -> RouteReference | None:
        """Return one bound route reference."""
        return self.items.get(offer_id)

    def get_many(
        self,
        offer_ids: tuple[str, ...],
    ) -> dict[str, RouteReference]:
        """Return existing bindings for the requested offers."""
        return {
            offer_id: self.items[offer_id]
            for offer_id in offer_ids
            if offer_id in self.items
        }

    def replace(
        self,
        references: tuple[tuple[str, RouteReference], ...],
    ) -> None:
        """Replace all bindings like the relational implementation."""
        self.items = dict(references)


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
