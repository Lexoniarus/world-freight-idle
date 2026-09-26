"""Derived routing-anchor domain values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.geography import Coordinates
from app.domain.validation import require_finite, require_identity

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
    status: RoutingAnchorStatus
