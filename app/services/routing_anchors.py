"""Collect real access candidates; only connection proofs publish anchors."""

import logging
from collections.abc import Callable
from dataclasses import replace

from app.domain.errors import GeocodingError, RoutingError
from app.domain.geography import Coordinates
from app.domain.ports import Geocoder
from app.domain.readiness_ports import RoutingReadinessStore
from app.domain.routing_anchor_ports import (
    RoutingAnchorStore,
    TruckAnchorLocator,
)
from app.domain.routing_anchors import (
    MAX_CANDIDATES,
    POSITIVE_TTL,
    RoutingCandidate,
    anchor_source_fingerprint,
    distance_m,
)
from app.domain.routing_readiness import RoutingAttempt
from app.domain.world import Facility
from app.tracing import get_trace_id


class RoutingAnchorResolver:
    """Read bounded candidates without prematurely mutating shared anchors."""

    def __init__(
        self,
        store: RoutingAnchorStore,
        locator: TruckAnchorLocator,
        geocoder: Geocoder,
        max_snap_distance_m: float,
        clock: Callable[[], float],
        evidence: RoutingReadinessStore | None = None,
        provider_revision: Callable[[], str | None] | None = None,
    ) -> None:
        """Inject provider ports and connection policy dependencies."""
        if not 0 < max_snap_distance_m <= 1000:
            raise ValueError(
                "Maximum snap distance must be positive and <= 1000."
            )
        self._store = store
        self._locator = locator
        self._geocoder = geocoder
        self.max_snap_distance_m = max_snap_distance_m
        self._clock = clock
        self._evidence = evidence
        self._provider_revision = provider_revision

    async def resolve(
        self,
        facility: Facility,
        *,
        force: bool = False,
    ) -> tuple[RoutingCandidate, ...]:
        """Prefer certified access; force also searches the postal address."""
        original = facility.coordinates
        cached = self._store.get(facility.facility_uid, "truck")
        candidates: list[RoutingCandidate] = []
        if cached and cached.anchor and original:
            separation = distance_m(original, cached.anchor)
            if separation <= self.max_snap_distance_m:
                revision = (
                    self._provider_revision()
                    if self._provider_revision
                    else cached.provider_revision
                )
                candidates.append(
                    RoutingCandidate(
                        cached.anchor,
                        separation,
                        cached.provider,
                        revision,
                        cached.method,
                    )
                )
                if (
                    cached.source_fingerprint
                    == anchor_source_fingerprint(
                        facility, self.max_snap_distance_m
                    )
                    and cached.provider_revision == revision
                    and self._clock() - cached.validated_at < POSITIVE_TTL
                ):
                    return tuple(candidates)
        if original:
            candidates.extend(
                await self._locate(
                    facility, original, original, "facility_coordinate"
                )
            )
        if force or not candidates:
            try:
                lat, lon, _ = await self._geocoder.geocode(
                    facility.address.display_text()
                )
                address = Coordinates(lat, lon)
                candidates.extend(
                    await self._locate(
                        facility,
                        address,
                        original or address,
                        "address_fallback",
                    )
                )
            except GeocodingError as error:
                self._record(facility, "address_fallback", str(error))
                if error.retryable:
                    raise RoutingError(
                        "Address provider unavailable."
                    ) from error
        unique: dict[Coordinates, RoutingCandidate] = {}
        for candidate in candidates:
            unique.setdefault(candidate.coordinates, candidate)
        preferred = cached.anchor if cached else None
        return tuple(
            sorted(
                unique.values(),
                key=lambda item: (
                    item.coordinates != preferred,
                    item.distance_m,
                ),
            )[:MAX_CANDIDATES]
        )

    async def _locate(
        self,
        facility: Facility,
        point: Coordinates,
        original: Coordinates,
        method: str,
    ) -> tuple[RoutingCandidate, ...]:
        """Bound every provider candidate against the original facility."""
        located = await self._locator.locate(point)
        self._record(
            facility,
            method,
            located.status,
            located.provider_code,
            located.provider_message,
        )
        if located.status in {"provider_unavailable", "invalid_response"}:
            raise RoutingError("Truck access provider unavailable or invalid.")
        return tuple(
            replace(candidate, distance_m=separation, method=method)
            for candidate in located.candidates
            if (separation := distance_m(original, candidate.coordinates))
            <= self.max_snap_distance_m
        )

    def _record(
        self,
        facility: Facility,
        method: str,
        outcome: str,
        provider_code: int | None = None,
        provider_message: str | None = None,
    ) -> None:
        """Retain append-only search evidence without certifying a road."""
        logging.getLogger(__name__).info(
            "Truck access candidate search",
            extra={
                "event": "routing_anchor.candidates",
                "data": {
                    "facility_uid": facility.facility_uid,
                    "method": method,
                    "outcome": outcome,
                },
            },
        )
        if self._evidence:
            self._evidence.append_attempt(
                RoutingAttempt(
                    facility.facility_uid,
                    method,
                    outcome,
                    self._clock(),
                    get_trace_id(),
                    provider_code=provider_code,
                    provider_message=provider_message,
                )
            )
