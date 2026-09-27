"""Resolve bounded truck access candidates without moving facilities."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import replace

from app.domain.errors import GeocodingError
from app.domain.geography import Coordinates
from app.domain.ports import Geocoder
from app.domain.readiness_ports import RoutingReadinessStore
from app.domain.routing_anchor_ports import (
    RoutingAnchorStore,
    TruckAnchorLocator,
)
from app.domain.routing_anchors import (
    LocateResult,
    RoutingAnchor,
    anchor_source_fingerprint,
)
from app.domain.routing_readiness import RoutingAttempt
from app.domain.world import Facility
from app.tracing import get_trace_id


class RoutingAnchorResolver:
    """Resolve globally leased anchors and preserve each attempt's evidence."""

    def __init__(
        self,
        store: RoutingAnchorStore,
        locator: TruckAnchorLocator,
        geocoder: Geocoder,
        max_snap_distance_m: float,
        clock: Callable[[], float],
        evidence: RoutingReadinessStore | None = None,
    ) -> None:
        """Inject provider ports and optional infrastructure diagnostics."""
        if max_snap_distance_m <= 0:
            raise ValueError("Maximum snap distance must be positive.")
        self._store = store
        self._locator = locator
        self._geocoder = geocoder
        self._max_snap_distance_m = max_snap_distance_m
        self._clock = clock
        self._evidence = evidence

    async def resolve(
        self, facility: Facility, *, force: bool = False
    ) -> RoutingAnchor:
        """Reuse a validated anchor or acquire globally bounded repair work."""
        subject = f"anchor:{facility.facility_uid}:truck"
        owner = uuid.uuid4().hex
        async with asyncio.timeout(90):
            while True:
                cached = self._store.get(facility.facility_uid, "truck")
                if (
                    not force
                    and cached is not None
                    and cached.validation_status == "validated"
                    and cached.facility_coordinates == facility.coordinates
                    and cached.source_fingerprint
                    == anchor_source_fingerprint(facility)
                ):
                    return cached
                if self._evidence is None or self._evidence.acquire(
                    subject, owner, self._clock(), self._clock() + 100
                ):
                    break
                await asyncio.sleep(0.1)
            try:
                result = replace(
                    await self._repair(facility),
                    source_fingerprint=anchor_source_fingerprint(facility),
                )
                if self._evidence is None:
                    self._store.put(result)
                elif not self._store.put_leased(result, owner, self._clock()):
                    raise TimeoutError(
                        "Anchor lease expired before publication."
                    )
                return result
            finally:
                if self._evidence is not None:
                    self._evidence.release(subject, owner)

    async def _repair(self, facility: Facility) -> RoutingAnchor:
        """Try facility, postal address and bounded real OSM candidates."""
        candidates: list[Coordinates] = []
        attempted: set[Coordinates] = set()
        if facility.coordinates is not None:
            attempted.add(facility.coordinates)
            result, located = await self._attempt(
                facility, facility.coordinates, "facility_coordinate"
            )
            candidates.extend(located.candidates)
            if result.validation_status in {
                "validated",
                "provider_unavailable",
            }:
                return result
        try:
            lat, lon, _ = await self._geocoder.geocode(
                facility.address.display_text()
            )
            coordinate = Coordinates(lat, lon)
            attempted.add(coordinate)
            result, located = await self._attempt(
                facility, coordinate, "address_fallback"
            )
            candidates.extend(located.candidates)
            if result.validation_status in {
                "validated",
                "provider_unavailable",
            }:
                return result
        except GeocodingError as error:
            result = RoutingAnchor(
                facility.facility_uid,
                "truck",
                None,
                "address_fallback",
                facility.coordinates,
                None,
                "provider_unavailable"
                if error.retryable
                else "geocoding_failed",
                "Nominatim + Valhalla",
                None,
                self._clock(),
            )
            self._record(result, None, None, str(error))
            if error.retryable:
                return result
        unique = tuple(dict.fromkeys(candidates))
        for candidate in unique[:5]:
            if candidate in attempted:
                continue
            attempted.add(candidate)
            result, _ = await self._attempt(facility, candidate, "osm_access")
            if result.validation_status in {
                "validated",
                "provider_unavailable",
            }:
                break
        return result

    async def _attempt(
        self,
        facility: Facility,
        candidate: Coordinates,
        method: str,
    ) -> tuple[RoutingAnchor, LocateResult]:
        """Validate a candidate and append evidence before returning it."""
        located = await self._locator.locate(candidate)
        result = self._accepted_anchor(
            facility, facility.coordinates, located, method
        ) or self._failure(facility, facility.coordinates, located, method)
        self._record(
            result, candidate, located.provider_code, located.provider_message
        )
        return result, located

    def _record(
        self,
        result: RoutingAnchor,
        candidate: Coordinates | None,
        code: int | None,
        message: str | None,
    ) -> None:
        """Append an attempt without overwriting earlier repair evidence."""
        success = result.validation_status == "validated"
        logging.getLogger(__name__).log(
            logging.INFO if success else logging.WARNING,
            "Truck anchor attempt completed",
            extra={
                "event": "routing_anchor.resolved"
                if success
                else "routing_anchor.failure",
                "data": {
                    "facility_uid": result.facility_uid,
                    "method": result.method,
                    "status": result.validation_status,
                },
            },
        )
        if self._evidence is not None:
            self._evidence.append_attempt(
                RoutingAttempt(
                    result.facility_uid,
                    result.method,
                    result.validation_status,
                    self._clock(),
                    get_trace_id(),
                    candidate.latitude if candidate else None,
                    candidate.longitude if candidate else None,
                    code,
                    message,
                )
            )

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
