"""Resolve global facility routing anchors without mutating display data."""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.domain.errors import GeocodingError
from app.domain.geography import Coordinates
from app.domain.ports import Geocoder
from app.domain.routing_anchor_ports import (
    RoutingAnchorStore,
    TruckAnchorLocator,
)
from app.domain.routing_anchors import LocateResult, RoutingAnchor
from app.domain.world import Facility

LOGGER = logging.getLogger(__name__)


class RoutingAnchorResolver:
    """Resolve and persist one truck-routing anchor per facility."""

    def __init__(
        self,
        store: RoutingAnchorStore,
        locator: TruckAnchorLocator,
        geocoder: Geocoder,
        max_snap_distance_m: float,
        clock: Callable[[], float],
    ) -> None:
        if max_snap_distance_m <= 0:
            raise ValueError("Maximum snap distance must be positive.")
        self._store = store
        self._locator = locator
        self._geocoder = geocoder
        self._max_snap_distance_m = max_snap_distance_m
        self._clock = clock

    async def resolve(self, facility: Facility) -> RoutingAnchor:
        """Resolve an anchor without changing display coordinates."""
        cached = self._store.get(facility.facility_uid, "truck")
        if (
            cached is not None
            and cached.validation_status == "validated"
            and cached.facility_coordinates == facility.coordinates
        ):
            LOGGER.info(
                "Routing anchor cache hit",
                extra={
                    "event": "routing_anchor.cache_hit",
                    "data": {"facility_uid": facility.facility_uid},
                },
            )
            return cached

        original = facility.coordinates
        if original is not None:
            direct = await self._locator.locate(original)
            accepted = self._accepted_anchor(
                facility,
                original,
                direct,
                "facility_coordinate",
            )
            if accepted is not None:
                self._store.put(accepted)
                LOGGER.info(
                    "Routing anchor resolved",
                    extra={
                        "event": "routing_anchor.resolved",
                        "data": {
                            "facility_uid": facility.facility_uid,
                            "method": accepted.method,
                            "status": accepted.validation_status,
                            "snap_distance_m": accepted.snap_distance_m,
                            "provider": accepted.provider,
                        },
                    },
                )
                return accepted
            if direct.status == "provider_unavailable":
                failure = self._failure(
                    facility,
                    original,
                    direct,
                    "facility_coordinate",
                )
                self._store.put(failure)
                LOGGER.warning(
                    "Routing anchor resolution failed",
                    extra={
                        "event": "routing_anchor.failure",
                        "data": {
                            "facility_uid": facility.facility_uid,
                            "method": failure.method,
                            "status": failure.validation_status,
                            "provider": failure.provider,
                        },
                    },
                )
                return failure

        address = facility.address.display_text()
        try:
            latitude, longitude, _ = await self._geocoder.geocode(address)
        except GeocodingError:
            failure = RoutingAnchor(
                facility_uid=facility.facility_uid,
                routing_profile="truck",
                anchor=None,
                method="address_fallback",
                facility_coordinates=original,
                snap_distance_m=None,
                validation_status="geocoding_failed",
                provider="Nominatim + Valhalla",
                provider_revision=None,
                validated_at=self._clock(),
            )
            self._store.put(failure)
            LOGGER.warning(
                "Routing anchor resolution failed",
                extra={
                    "event": "routing_anchor.failure",
                    "data": {
                        "facility_uid": facility.facility_uid,
                        "method": failure.method,
                        "status": failure.validation_status,
                        "provider": failure.provider,
                    },
                },
            )
            return failure

        geocoded = Coordinates(latitude, longitude)
        located = await self._locator.locate(geocoded)
        accepted = self._accepted_anchor(
            facility,
            original,
            located,
            "address_fallback",
        )
        if accepted is not None:
            self._store.put(accepted)
            LOGGER.info(
                "Routing anchor resolved",
                extra={
                    "event": "routing_anchor.resolved",
                    "data": {
                        "facility_uid": facility.facility_uid,
                        "method": accepted.method,
                        "status": accepted.validation_status,
                        "snap_distance_m": accepted.snap_distance_m,
                        "provider": accepted.provider,
                    },
                },
            )
            return accepted
        failure = self._failure(
            facility,
            original,
            located,
            "address_fallback",
        )
        self._store.put(failure)
        LOGGER.warning(
            "Routing anchor resolution failed",
            extra={
                "event": "routing_anchor.failure",
                "data": {
                    "facility_uid": facility.facility_uid,
                    "method": failure.method,
                    "status": failure.validation_status,
                    "snap_distance_m": failure.snap_distance_m,
                    "provider": failure.provider,
                },
            },
        )
        return failure

    def _accepted_anchor(
        self,
        facility: Facility,
        original: Coordinates | None,
        located: LocateResult,
        method: str,
    ) -> RoutingAnchor | None:
        """Accept an anchor only within the snap-distance limit."""
        if not located.accepted or located.coordinates is None:
            return None
        distance = located.snap_distance_m
        if distance is not None and distance > self._max_snap_distance_m:
            return None
        return RoutingAnchor(
            facility_uid=facility.facility_uid,
            routing_profile="truck",
            anchor=located.coordinates,
            method=method,
            facility_coordinates=original,
            snap_distance_m=distance,
            validation_status="validated",
            provider=located.provider,
            provider_revision=located.provider_revision,
            validated_at=self._clock(),
        )

    def _failure(
        self,
        facility: Facility,
        original: Coordinates | None,
        located: LocateResult,
        method: str,
    ) -> RoutingAnchor:
        """Classify failure without storing fake coordinates."""
        status = located.status
        if (
            located.accepted
            and located.snap_distance_m is not None
            and located.snap_distance_m > self._max_snap_distance_m
        ):
            status = "snap_too_far"
        return RoutingAnchor(
            facility_uid=facility.facility_uid,
            routing_profile="truck",
            anchor=None,
            method=method,
            facility_coordinates=original,
            snap_distance_m=located.snap_distance_m,
            validation_status=status,
            provider=located.provider,
            provider_revision=located.provider_revision,
            validated_at=self._clock(),
        )
