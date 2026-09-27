from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from app.domain.errors import RoutingError
from app.domain.geography import Coordinates
from app.domain.routing_anchors import RoutingCandidate
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
    max_snap_distance_m = 1000.0

    def __init__(self, failed_uid: str | None = None) -> None:
        self.failed_uid = failed_uid

    async def resolve(self, facility: Facility, *, force: bool = False):
        if facility.facility_uid == self.failed_uid:
            return ()
        assert facility.coordinates is not None
        return (
            RoutingCandidate(
                Coordinates(
                    facility.coordinates.latitude + 0.001,
                    facility.coordinates.longitude + 0.001,
                ),
                150.0,
                "fake",
                None,
            ),
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
            start.coordinates.latitude + 0.001,
            start.coordinates.longitude + 0.001,
            destination.coordinates.latitude + 0.001,
            destination.coordinates.longitude + 0.001,
        ),
        (
            destination.coordinates.latitude + 0.001,
            destination.coordinates.longitude + 0.001,
            start.coordinates.latitude + 0.001,
            start.coordinates.longitude + 0.001,
        ),
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

    with pytest.raises(RoutingError, match="Truck-Routing-Anchor"):
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

    calls: dict[str, int] = {}
    resolve = planner.anchors.resolve

    async def changing_candidates(facility, *, force=False):
        count = calls.get(facility.facility_uid, 0)
        calls[facility.facility_uid] = count + 1
        candidates = await resolve(facility, force=force)
        return tuple(
            replace(
                candidate,
                coordinates=Coordinates(
                    candidate.coordinates.latitude + count * 0.001,
                    candidate.coordinates.longitude,
                ),
            )
            for candidate in candidates
        )

    with patch.object(
        planner.anchors, "resolve", side_effect=changing_candidates
    ):
        route = await planner.route(start, offer)

    assert route.approach is not None
    assert len(router.calls) == 4
    assert calls[origin_uid] == 1
    assert route.approach.coordinates[-1] == route.delivery.coordinates[0]
