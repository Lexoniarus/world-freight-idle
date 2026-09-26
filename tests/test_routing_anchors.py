from __future__ import annotations

import pytest

from app.domain.errors import GeocodingError
from app.domain.geography import Address, City, Coordinates, Country
from app.domain.routing_anchors import (
    LocateResult,
    RoutingAnchor,
    RoutingAnchorStatus,
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


def test_routing_anchor_resolver_rejects_nonpositive_snap_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        RoutingAnchorResolver(
            MemoryAnchorStore(),
            FakeLocator([]),
            FakeGeocoder(),
            0,
            lambda: 0.0,
        )


@pytest.mark.asyncio
async def test_routing_anchor_direct_facility_coordinate_works(caplog) -> None:
    caplog.set_level("INFO")
    item = facility()
    assert item.coordinates is not None
    store = MemoryAnchorStore()
    locator = FakeLocator(
        [located(distance=0.0, coordinates=item.coordinates)]
    )
    geocoder = FakeGeocoder()
    resolver = RoutingAnchorResolver(
        store,
        locator,
        geocoder,
        250.0,
        lambda: 1.0,
    )

    result = await resolver.resolve(item)

    assert result.validation_status == "validated"
    assert result.method == "facility_coordinate"
    assert result.anchor == item.coordinates
    assert geocoder.calls == []
    assert any(
        getattr(record, "event", None) == "routing_anchor.resolved"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_routing_anchor_valhalla_snap_works() -> None:
    item = facility()
    store = MemoryAnchorStore()
    locator = FakeLocator([located(distance=42.0)])
    resolver = RoutingAnchorResolver(
        store,
        locator,
        FakeGeocoder(),
        250.0,
        lambda: 2.0,
    )

    result = await resolver.resolve(item)

    assert result.anchor == Coordinates(52.5201, 13.4051)
    assert result.snap_distance_m == 42.0
    assert result.facility_coordinates == item.coordinates


@pytest.mark.asyncio
async def test_routing_anchor_address_fallback_works() -> None:
    item = facility()
    store = MemoryAnchorStore()
    locator = FakeLocator(
        [
            located(
                accepted=False,
                status="no_truck_edge",
                coordinates=None,
            ),
            located(
                distance=30.0,
                coordinates=Coordinates(52.51, 13.41),
            ),
        ]
    )
    geocoder = FakeGeocoder((52.509, 13.409, "resolved"))
    resolver = RoutingAnchorResolver(
        store,
        locator,
        geocoder,
        250.0,
        lambda: 3.0,
    )

    result = await resolver.resolve(item)

    assert result.validation_status == "validated"
    assert result.method == "address_fallback"
    assert geocoder.calls == [item.address.display_text()]
    assert len(locator.calls) == 2


@pytest.mark.asyncio
async def test_routing_anchor_without_display_coordinate_uses_address() -> (
    None
):
    item = facility(None)
    locator = FakeLocator([located(coordinates=Coordinates(52.51, 13.41))])
    resolver = RoutingAnchorResolver(
        MemoryAnchorStore(),
        locator,
        FakeGeocoder((52.509, 13.409, "resolved")),
        250.0,
        lambda: 3.5,
    )

    result = await resolver.resolve(item)

    assert result.method == "address_fallback"
    assert result.facility_coordinates is None


@pytest.mark.asyncio
async def test_routing_anchor_geocoding_failure_is_persisted() -> None:
    item = facility()
    store = MemoryAnchorStore()
    locator = FakeLocator(
        [
            located(
                accepted=False,
                status="no_truck_edge",
                coordinates=None,
            )
        ]
    )
    resolver = RoutingAnchorResolver(
        store,
        locator,
        FakeGeocoder(error=GeocodingError("offline")),
        250.0,
        lambda: 3.75,
    )

    result = await resolver.resolve(item)

    assert result.validation_status == "geocoding_failed"
    assert result.anchor is None
    assert store.get(item.facility_uid, "truck") == result


@pytest.mark.asyncio
async def test_routing_anchor_too_large_snap_is_rejected() -> None:
    item = facility()
    store = MemoryAnchorStore()
    locator = FakeLocator(
        [
            located(distance=500.0),
            located(distance=600.0),
        ]
    )
    resolver = RoutingAnchorResolver(
        store,
        locator,
        FakeGeocoder(),
        100.0,
        lambda: 4.0,
    )

    result = await resolver.resolve(item)

    assert result.anchor is None
    assert result.validation_status == "snap_too_far"


@pytest.mark.asyncio
async def test_routing_anchor_no_truck_edge_is_persisted(caplog) -> None:
    caplog.set_level("WARNING")
    item = facility()
    store = MemoryAnchorStore()
    locator = FakeLocator(
        [
            located(
                accepted=False,
                status="no_truck_edge",
                coordinates=None,
            ),
            located(
                accepted=False,
                status="no_truck_edge",
                coordinates=None,
            ),
        ]
    )
    resolver = RoutingAnchorResolver(
        store,
        locator,
        FakeGeocoder(),
        250.0,
        lambda: 5.0,
    )

    result = await resolver.resolve(item)

    assert result.anchor is None
    assert result.validation_status == "no_truck_edge"
    assert store.get(item.facility_uid, "truck") == result
    assert any(
        getattr(record, "event", None) == "routing_anchor.failure"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_routing_anchor_provider_temporarily_offline() -> None:
    item = facility()
    store = MemoryAnchorStore()
    locator = FakeLocator(
        [
            located(
                accepted=False,
                status="provider_unavailable",
                coordinates=None,
                distance=None,
            )
        ]
    )
    geocoder = FakeGeocoder()
    resolver = RoutingAnchorResolver(
        store,
        locator,
        geocoder,
        250.0,
        lambda: 6.0,
    )

    result = await resolver.resolve(item)

    assert result.validation_status == "provider_unavailable"
    assert result.anchor is None
    assert geocoder.calls == []


@pytest.mark.asyncio
async def test_routing_anchor_cached_validated_anchor_is_reused() -> None:
    item = facility()
    store = MemoryAnchorStore()
    cached = RoutingAnchor(
        facility_uid=item.facility_uid,
        routing_profile="truck",
        anchor=Coordinates(52.6, 13.5),
        method="facility_coordinate",
        facility_coordinates=item.coordinates,
        snap_distance_m=20.0,
        validation_status="validated",
        provider="Valhalla",
        provider_revision="graph-1",
        validated_at=7.0,
    )
    store.put(cached)
    locator = FakeLocator([])
    resolver = RoutingAnchorResolver(
        store,
        locator,
        FakeGeocoder(),
        250.0,
        lambda: 8.0,
    )

    result = await resolver.resolve(item)

    assert result == cached
    assert locator.calls == []


@pytest.mark.asyncio
async def test_routing_anchor_does_not_mutate_display_coordinate() -> None:
    item = facility()
    before = item.coordinates
    locator = FakeLocator([located(distance=25.0)])
    resolver = RoutingAnchorResolver(
        MemoryAnchorStore(),
        locator,
        FakeGeocoder(),
        250.0,
        lambda: 9.0,
    )

    result = await resolver.resolve(item)

    assert result.anchor != before
    assert item.coordinates == before
