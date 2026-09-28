from __future__ import annotations

import pytest

from app.domain.errors import GeocodingError
from app.domain.geography import Address, City, Coordinates, Country
from app.domain.routing_anchors import (
    LocateResult,
    RoutingAnchor,
    RoutingAnchorStatus,
    RoutingCandidate,
    anchor_source_fingerprint,
)
from app.domain.world import Facility
from app.services.routing_anchors import RoutingAnchorResolver


class MemoryAnchorStore:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], RoutingAnchor] = {}

    def get(
        self,
        facility_uid: str,
        routing_profile: str,
    ) -> RoutingAnchor | None:
        return self.items.get((facility_uid, routing_profile))

    def put(self, anchor: RoutingAnchor) -> None:
        self.items[(anchor.facility_uid, anchor.routing_profile)] = anchor

    def put_leased(
        self, anchor: RoutingAnchor, owner: str, now: float
    ) -> bool:
        self.put(anchor)
        return True


class FakeLocator:
    def __init__(self, results: list[LocateResult]) -> None:
        self.results = results
        self.calls: list[Coordinates] = []

    async def locate(self, coordinates: Coordinates) -> LocateResult:
        self.calls.append(coordinates)
        return self.results.pop(0)


class FakeGeocoder:
    def __init__(
        self,
        result: tuple[float, float, str] = (52.5, 13.4, "resolved"),
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    async def geocode(self, address: str) -> tuple[float, float, str]:
        self.calls.append(address)
        if self.error is not None:
            raise self.error
        return self.result


def facility(
    coordinates: Coordinates | None = Coordinates(52.52, 13.405),
) -> Facility:
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


def test_routing_anchor_rejects_coordinate_status_mismatches() -> None:
    with pytest.raises(ValueError, match="requires coordinates"):
        RoutingAnchor(
            facility_uid="facility-1",
            routing_profile="truck",
            anchor=None,
            method="facility_coordinate",
            facility_coordinates=Coordinates(52.5, 13.4),
            snap_distance_m=0.0,
            validation_status="validated",
            provider="Valhalla",
            provider_revision=None,
            validated_at=1.0,
        )
    with pytest.raises(ValueError, match="must not store"):
        RoutingAnchor(
            facility_uid="facility-1",
            routing_profile="truck",
            anchor=Coordinates(52.5, 13.4),
            method="facility_coordinate",
            facility_coordinates=Coordinates(52.5, 13.4),
            snap_distance_m=0.0,
            validation_status="no_truck_edge",
            provider="Valhalla",
            provider_revision=None,
            validated_at=1.0,
        )


@pytest.mark.parametrize("limit", [0, -1, 1000.01, float("nan")])
def test_routing_anchor_resolver_rejects_nonpositive_snap_limit(limit) -> None:
    with pytest.raises(ValueError, match="positive"):
        RoutingAnchorResolver(
            MemoryAnchorStore(),
            FakeLocator([]),
            FakeGeocoder(),
            limit,
            lambda: 0.0,
        )


@pytest.mark.asyncio
async def test_candidates_never_publish_before_connection_proof():
    item = facility()
    store = MemoryAnchorStore()
    locator = FakeLocator([located(coordinates=item.coordinates)])
    geocoder = FakeGeocoder()
    resolver = RoutingAnchorResolver(store, locator, geocoder, 1000, lambda: 1)
    result = await resolver.resolve(item)
    assert result[0].coordinates == item.coordinates
    assert store.items == {}
    assert geocoder.calls == []
    assert item.coordinates == Coordinates(52.52, 13.405)


@pytest.mark.asyncio
async def test_candidate_bound_uses_original_location_even_after_address_snap():
    item = facility()
    distant = Coordinates(52.54, 13.405)
    locator = FakeLocator(
        [located(coordinates=distant), located(coordinates=distant)]
    )
    resolver = RoutingAnchorResolver(
        MemoryAnchorStore(),
        locator,
        FakeGeocoder((52.54, 13.405, "resolved")),
        1000,
        lambda: 1,
    )
    assert await resolver.resolve(item) == ()


@pytest.mark.asyncio
async def test_address_and_missing_coordinate_fallbacks_are_bounded():
    point = Coordinates(52.5202, 13.405)
    locator = FakeLocator(
        [located(accepted=False), located(coordinates=point)]
    )
    resolver = RoutingAnchorResolver(
        MemoryAnchorStore(),
        locator,
        FakeGeocoder((52.52, 13.405, "resolved")),
        1000,
        lambda: 1,
    )
    result = await resolver.resolve(facility())
    assert result[0].method == "address_fallback"
    assert 20 < result[0].distance_m < 25
    locator.results = [located(coordinates=point)]
    assert (await resolver.resolve(facility(None)))[
        0
    ].method == "address_fallback"


@pytest.mark.asyncio
async def test_candidate_provider_failures_and_geocoding_absence():
    from app.domain.errors import RoutingError

    for status in ("provider_unavailable", "invalid_response"):
        resolver = RoutingAnchorResolver(
            MemoryAnchorStore(),
            FakeLocator([located(accepted=False, status=status)]),
            FakeGeocoder(),
            1000,
            lambda: 1,
        )
        with pytest.raises(RoutingError):
            await resolver.resolve(facility())
    error = GeocodingError("no address")
    resolver = RoutingAnchorResolver(
        MemoryAnchorStore(),
        FakeLocator([located(accepted=False)]),
        FakeGeocoder(error=error),
        1000,
        lambda: 1,
    )
    assert await resolver.resolve(facility()) == ()
    error.retryable = True
    with pytest.raises(RoutingError):
        await resolver.resolve(facility(None))


@pytest.mark.asyncio
async def test_certified_access_is_stable_and_legacy_access_is_only_candidate():
    from dataclasses import replace

    item = facility()
    store = MemoryAnchorStore()
    cached = RoutingAnchor(
        item.facility_uid,
        "truck",
        item.coordinates,
        "facility_coordinate",
        item.coordinates,
        0,
        "validated",
        "test",
        None,
        1,
        anchor_source_fingerprint(item),
    )
    store.put(cached)
    locator = FakeLocator([])
    resolver = RoutingAnchorResolver(
        store, locator, FakeGeocoder(), 1000, lambda: 2
    )
    assert (await resolver.resolve(item, force=True))[
        0
    ].coordinates == item.coordinates
    assert not locator.calls
    store.put(replace(cached, source_fingerprint="old-locate-only"))
    locator.results = [located()]
    result = await resolver.resolve(item)
    assert result[0].coordinates == cached.anchor
    assert len(result) == 2
    store.put(replace(cached, anchor=Coordinates(53, 14)))
    locator.results = [located()]
    assert (await resolver.resolve(item))[0].coordinates != Coordinates(53, 14)
    store.put(cached)
    resolver._provider_revision = lambda: "new-graph"
    locator.results = [located()]
    assert len(await resolver.resolve(item)) == 2


def test_anchor_policy_changes_invalidate_coordinate_and_address_evidence():
    from dataclasses import replace

    item = facility()
    baseline = anchor_source_fingerprint(item)
    assert baseline == anchor_source_fingerprint(item, 1000)
    assert baseline != anchor_source_fingerprint(item, 250)
    assert baseline != anchor_source_fingerprint(
        replace(item, address=replace(item.address, street="changed"))
    )
    assert baseline != anchor_source_fingerprint(
        replace(item, coordinates=Coordinates(52.6, 13.4))
    )
