"""Derived routing-anchor domain values."""

from __future__ import annotations

import math
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from app.domain.geography import Coordinates
from app.domain.validation import require_finite, require_identity
from app.domain.world import Facility

VALIDATION_VERSION = "truck-connected-v2"
POSITIVE_TTL = 86_400.0
NEGATIVE_TTL = 3_600.0
ENDPOINT_TOLERANCE_M = 10.0
MAX_CANDIDATES = 5


def distance_m(first: Coordinates, second: Coordinates) -> float:
    """Measure actual WGS84 separation, independently of provider snaps."""
    lat1, lat2 = map(math.radians, (first.latitude, second.latitude))
    delta_lon = math.radians(second.longitude - first.longitude)
    value = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 12_742_017.6 * math.asin(math.sqrt(min(1.0, value)))


@dataclass(frozen=True, slots=True)
class RoutingCandidate:
    """A real road correlation, still requiring connection validation."""

    coordinates: Coordinates
    distance_m: float
    provider: str
    provider_revision: str | None
    method: str = "facility_coordinate"
    way_id: int | None = None
    inbound_reach: int | None = None
    outbound_reach: int | None = None


RoutingAnchorStatus = Literal[
    "validated",
    "no_truck_edge",
    "snap_too_far",
    "geocoding_failed",
    "provider_unavailable",
    "invalid_response",
]


@dataclass(frozen=True, slots=True)
class RoutingAnchor:
    """One persisted derived routing result for a facility and profile."""

    facility_uid: str
    routing_profile: str
    anchor: Coordinates | None
    method: str
    facility_coordinates: Coordinates | None
    snap_distance_m: float | None
    validation_status: RoutingAnchorStatus
    provider: str
    provider_revision: str | None
    validated_at: float
    source_fingerprint: str | None = None

    def __post_init__(self) -> None:
        """Validate routing-anchor facts without mutating catalogue values."""
        require_identity(self.facility_uid, "Facility UID")
        require_identity(self.routing_profile, "Routing profile")
        require_identity(self.method, "Anchor method")
        require_identity(self.validation_status, "Validation status")
        require_identity(self.provider, "Provider")
        require_finite(self.validated_at, "Validated at", 0)
        if self.snap_distance_m is not None:
            require_finite(self.snap_distance_m, "Snap distance", 0)
        if self.validation_status == "validated" and self.anchor is None:
            raise ValueError("Validated routing anchor requires coordinates.")
        if self.validation_status != "validated" and self.anchor is not None:
            raise ValueError(
                "Failed routing anchor must not store coordinates."
            )


@dataclass(frozen=True, slots=True)
class LocateResult:
    """Normalized truck-locate result returned by the Valhalla provider."""

    accepted: bool
    coordinates: Coordinates | None
    snap_distance_m: float | None
    provider: str
    provider_revision: str | None
    status: RoutingAnchorStatus | Literal["located"]
    candidates: tuple[RoutingCandidate, ...] = ()
    provider_code: int | None = None
    provider_message: str | None = None


def anchor_source_fingerprint(
    facility: Facility, maximum_distance_m: float = 1000.0
) -> str:
    """Bind cached access to facility identity, address and coordinates."""
    value = (
        VALIDATION_VERSION,
        float(maximum_distance_m),
        facility.facility_uid,
        facility.address.display_text(),
        facility.coordinates,
    )
    return sha256(repr(value).encode()).hexdigest()
