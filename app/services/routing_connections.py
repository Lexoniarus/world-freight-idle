"""Validate real two-way connections before any anchor publication."""

import asyncio
import logging
from collections.abc import Callable
from itertools import product

from app.domain.errors import RoutingError
from app.domain.geography import Coordinates
from app.domain.ports import TruckRouter
from app.domain.routes import RouteSnapshot
from app.domain.routing_anchor_ports import RoutingAnchorResolverPort
from app.domain.routing_anchors import (
    ENDPOINT_TOLERANCE_M,
    MAX_CANDIDATES,
    RoutingAnchor,
    RoutingCandidate,
    anchor_source_fingerprint,
    distance_m,
)
from app.domain.routing_connections import ValidatedConnection
from app.domain.routing_readiness import RoutingAttempt, relation_identity
from app.domain.world import Facility
from app.tracing import get_trace_id


class RoutingConnectionValidator:
    """Own bounded candidate trials; callers own leases and persistence."""

    async def validate(
        self,
        origin: Facility,
        destination: Facility,
        router: TruckRouter,
        anchors: RoutingAnchorResolverPort,
        clock: Callable[[], float],
        record: Callable[[RoutingAttempt], None] | None = None,
        fixed: dict[str, RoutingCandidate] | None = None,
    ) -> ValidatedConnection:
        """Require real return access without reversing a route polyline."""
        try:
            async with asyncio.timeout(120):
                return await self._search(
                    origin,
                    destination,
                    router,
                    anchors,
                    clock,
                    record,
                    fixed or {},
                )
        except TimeoutError as error:
            raise RoutingError("Connection preparation timed out.") from error

    async def _search(
        self,
        origin: Facility,
        destination: Facility,
        router: TruckRouter,
        anchors: RoutingAnchorResolverPort,
        clock: Callable[[], float],
        record: Callable[[RoutingAttempt], None] | None,
        fixed: dict[str, RoutingCandidate],
    ) -> ValidatedConnection:
        """Try local candidates before the bounded postal-address fallback."""
        attempted: set[tuple[Coordinates, Coordinates]] = set()
        candidates: dict[str, dict[Coordinates, RoutingCandidate]] = {
            origin.facility_uid: {},
            destination.facility_uid: {},
        }
        error = RoutingError("Facility besitzt keinen Truck-Routing-Anchor.")
        error.category = "endpoint_unreachable"
        for fallback in (False, True):
            for facility in (origin, destination):
                selected = candidates[facility.facility_uid]
                if len(selected) >= MAX_CANDIDATES:
                    continue
                available = (
                    (fixed[facility.facility_uid],)
                    if facility.facility_uid in fixed
                    else await anchors.resolve(facility, force=fallback)
                )
                for candidate in available:
                    if len(selected) >= MAX_CANDIDATES:
                        break
                    selected.setdefault(candidate.coordinates, candidate)
            starts = tuple(candidates[origin.facility_uid].values())
            ends = tuple(candidates[destination.facility_uid].values())
            pairs = sorted(
                product(enumerate(starts), enumerate(ends)),
                key=lambda pair: (
                    (pair[0][0] != 0) + (pair[1][0] != 0),
                    pair[0][1].distance_m + pair[1][1].distance_m,
                ),
            )
            for (_, start), (_, end) in pairs:
                key = start.coordinates, end.coordinates
                if key in attempted:
                    continue
                attempted.add(key)
                try:
                    forward = await self._route(
                        origin.facility_uid,
                        destination.facility_uid,
                        start,
                        end,
                        router,
                        clock,
                        record,
                    )
                    reverse = await self._route(
                        destination.facility_uid,
                        origin.facility_uid,
                        end,
                        start,
                        router,
                        clock,
                        record,
                    )
                except RoutingError as failure:
                    error = failure
                    if error.category not in {
                        "no_path",
                        "endpoint_unreachable",
                        "endpoint_mismatch",
                    }:
                        raise
                    continue
                return ValidatedConnection(
                    self._anchor(origin, start, clock(), anchors),
                    self._anchor(destination, end, clock(), anchors),
                    forward,
                    reverse,
                )
            if len(attempted) >= 25:
                raise RoutingError("Connection repair budget exhausted.")
        raise error

    async def _route(
        self,
        origin: str,
        destination: str,
        start: RoutingCandidate,
        end: RoutingCandidate,
        router: TruckRouter,
        clock: Callable[[], float],
        record: Callable[[RoutingAttempt], None] | None,
    ) -> RouteSnapshot:
        """Check geometry and record each direction's provider evidence."""
        error = None
        route: RouteSnapshot | None = None
        try:
            route = await router.route(
                start.coordinates.latitude,
                start.coordinates.longitude,
                end.coordinates.latitude,
                end.coordinates.longitude,
            )
            first, last = route.coordinates[0], route.coordinates[-1]
            if (
                distance_m(Coordinates(first[1], first[0]), start.coordinates)
                > ENDPOINT_TOLERANCE_M
                or distance_m(Coordinates(last[1], last[0]), end.coordinates)
                > ENDPOINT_TOLERANCE_M
            ):
                mismatch = RoutingError("Route endpoints differ from anchors.")
                mismatch.category = "endpoint_mismatch"
                raise mismatch
        except RoutingError as failure:
            error = failure
        attempt = RoutingAttempt(
            relation_identity(origin, destination),
            "truck_connection",
            error.category if error else "validated",
            clock(),
            get_trace_id(),
            start.coordinates.latitude,
            start.coordinates.longitude,
            error.provider_code if error else None,
            error.provider_message if error else None,
        )
        logging.getLogger(__name__).info(
            "Truck connection direction checked",
            extra={
                "event": "routing_connection.checked",
                "data": {
                    "origin": origin,
                    "destination": destination,
                    "outcome": attempt.outcome,
                },
            },
        )
        if record:
            record(attempt)
        if error:
            raise error
        assert route is not None
        return route

    @staticmethod
    def _anchor(
        facility: Facility,
        candidate: RoutingCandidate,
        now: float,
        resolver: RoutingAnchorResolverPort,
    ) -> RoutingAnchor:
        """Certify a candidate only after the full connection succeeded."""
        return RoutingAnchor(
            facility.facility_uid,
            "truck",
            candidate.coordinates,
            candidate.method,
            facility.coordinates,
            candidate.distance_m,
            "validated",
            candidate.provider,
            candidate.provider_revision,
            now,
            anchor_source_fingerprint(facility, resolver.max_snap_distance_m),
        )
