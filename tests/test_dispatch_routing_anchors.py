from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from app.domain.geography import Coordinates
from app.domain.routing_anchors import RoutingAnchor
from app.domain.transports import RouteSnapshot
from app.domain.world import Facility
from app.services.cost_profiles import VehicleCostResolver
from app.services.dispatch_planning import DispatchPlanningService


class CaptureRouter:
    def __init__(self) -> None:
        self.calls: list[tuple[float, float, float, float]] = []

    async def route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteSnapshot:
        self.calls.append(
            (
                origin_lat,
                origin_lon,
                destination_lat,
                destination_lon,
            )
        )
        return RouteSnapshot(
            ((origin_lon, origin_lat), (destination_lon, destination_lat)),
            1.0,
            60.0,
            "capture",
        )


class OffsetAnchorResolver:
    def __init__(self, failed_uid: str | None = None) -> None:
        self.failed_uid = failed_uid

    async def resolve(self, facility: Facility) -> RoutingAnchor:
        if facility.facility_uid == self.failed_uid:
            return RoutingAnchor(
                facility_uid=facility.facility_uid,
                routing_profile="truck",
                anchor=None,
                method="facility_coordinate",
                facility_coordinates=facility.coordinates,
                snap_distance_m=None,
                validation_status="no_truck_edge",
                provider="fake",
                provider_revision=None,
                validated_at=1.0,
            )
        assert facility.coordinates is not None
        return RoutingAnchor(
            facility_uid=facility.facility_uid,
            routing_profile="truck",
            anchor=Coordinates(
                facility.coordinates.latitude + 0.01,
                facility.coordinates.longitude + 0.01,
            ),
            method="facility_coordinate",
            facility_coordinates=facility.coordinates,
            snap_distance_m=10.0,
            validation_status="validated",
            provider="fake",
            provider_revision="test",
            validated_at=1.0,
        )


@pytest.mark.asyncio
async def test_dispatch_routing_uses_anchors_not_display_coordinates(
    world_catalogue,
):
    facilities = [
        item
        for item in world_catalogue.read().facilities
        if item.coordinates is not None
    ]
    start, destination = facilities[:2]
    router = CaptureRouter()
    planner = DispatchPlanningService(
        router,
        MagicMock(spec=VehicleCostResolver),
        OffsetAnchorResolver(),
        world_catalogue,
    )

    await planner._route_between(
        start.location_snapshot(),
        destination.location_snapshot(),
    )

    assert start.coordinates is not None
    assert destination.coordinates is not None
    assert router.calls == [
        (
            start.coordinates.latitude + 0.01,
            start.coordinates.longitude + 0.01,
            destination.coordinates.latitude + 0.01,
            destination.coordinates.longitude + 0.01,
        )
    ]
    assert start.location_snapshot().coordinates == start.coordinates


@pytest.mark.asyncio
async def test_dispatch_routing_rejects_failed_anchor(world_catalogue):
    facilities = [
        item
        for item in world_catalogue.read().facilities
        if item.coordinates is not None
    ]
    start, destination = facilities[:2]
    planner = DispatchPlanningService(
        CaptureRouter(),
        MagicMock(spec=VehicleCostResolver),
        OffsetAnchorResolver(destination.facility_uid),
        world_catalogue,
    )

    with pytest.raises(ValueError, match="Truck-Routing-Anchor"):
        await planner._route_between(
            start.location_snapshot(),
            destination.location_snapshot(),
        )


@pytest.mark.asyncio
async def test_dispatch_approach_uses_facility_identity_not_display_coordinate(
    game,
):
    offer = game.state_repository.list_offers()[0]
    origin_uid = offer.origin.facility_uid
    same_city = [
        item
        for item in game.world.read().facilities
        if item.address.city.city_uid == offer.origin.city.city_uid
        and item.facility_uid != origin_uid
        and item.coordinates is not None
    ]
    assert same_city
    start = replace(
        same_city[0].location_snapshot(),
        coordinates=offer.origin.coordinates,
    )
    router = CaptureRouter()
    planner = DispatchPlanningService(
        router,
        game.dispatch_planning.costs,
        game.dispatch_planning.anchors,
        game.world,
    )

    route = await planner.route(start, offer)

    assert route.approach is not None
    assert len(router.calls) == 2
