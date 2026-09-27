"""Global routing facts, independent of player journeys and economics."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from app.domain.geography import Coordinates
from app.domain.routes import RouteSnapshot
from app.domain.validation import require_finite, require_identity

RelationStatus = Literal[
    "ready", "deterministic_failure", "transient_failure", "stale"
]


@dataclass(frozen=True, slots=True)
class RouteReference:
    """Identify one immutable revision of a directed global relation."""

    relation_id: str
    revision: str

    def __post_init__(self) -> None:
        """Reject references which cannot identify a persisted revision."""
        require_identity(self.relation_id, "Relation identity")
        require_identity(self.revision, "Relation revision")


@dataclass(frozen=True, slots=True)
class RoutePayload:
    """Retain provider metrics without final vehicle or game timing."""

    coordinates: tuple[tuple[float, float], ...]
    road_distance_km: float
    provider_duration_seconds: float
    provider: str

    def __post_init__(self) -> None:
        """Apply the existing geometry and provider metric invariants."""
        self.to_snapshot()

    def to_snapshot(self) -> RouteSnapshot:
        """Map provider facts without changing historical field names."""
        return RouteSnapshot(
            self.coordinates,
            self.road_distance_km,
            self.provider_duration_seconds,
            self.provider,
        )


@dataclass(frozen=True, slots=True)
class RoutingRelation:
    """Persist readiness for one directed facility pair and fingerprint."""

    reference: RouteReference
    origin_uid: str
    destination_uid: str
    fingerprint: str
    status: RelationStatus
    cache_key: str | None
    failure_category: str | None
    retry_at: float | None
    checked_at: float

    def __post_init__(self) -> None:
        """Reject incoherent ready and negative routing records."""
        for value in (self.origin_uid, self.destination_uid, self.fingerprint):
            require_identity(value, "Relation identity")
        if self.reference.relation_id != relation_identity(
            self.origin_uid, self.destination_uid
        ):
            raise ValueError(
                "Relation identity differs from its directed endpoints."
            )
        require_finite(self.checked_at, "Checked at", 0)
        if self.retry_at is not None:
            require_finite(self.retry_at, "Retry at", 0)
        if self.status not in {
            "ready",
            "deterministic_failure",
            "transient_failure",
            "stale",
        }:
            raise ValueError("Unknown relation status.")
        if self.status == "ready":
            if not self.cache_key or self.failure_category or self.retry_at:
                raise ValueError("Ready relation needs only a route payload.")
        elif self.cache_key is not None:
            raise ValueError("Non-ready relation cannot expose a payload.")


@dataclass(frozen=True, slots=True)
class RoutingAttempt:
    """Append-only evidence of one actual provider validation attempt."""

    subject_id: str
    method: str
    outcome: str
    observed_at: float
    trace_id: str
    candidate_lat: float | None = None
    candidate_lon: float | None = None
    provider_code: int | None = None
    provider_message: str | None = None

    def __post_init__(self) -> None:
        """Require identifiable diagnostic evidence and finite values."""
        for value in (
            self.subject_id,
            self.method,
            self.outcome,
            self.trace_id,
        ):
            require_identity(value, "Attempt identity")
        require_finite(self.observed_at, "Observed at", 0)
        if (self.candidate_lat is None) != (self.candidate_lon is None):
            raise ValueError("Attempt coordinates must be a complete pair.")
        if self.candidate_lat is not None and self.candidate_lon is not None:
            Coordinates(self.candidate_lat, self.candidate_lon)


def relation_identity(origin_uid: str, destination_uid: str) -> str:
    """Derive a stable directed truck relation identity."""
    require_identity(origin_uid, "Origin identity")
    require_identity(destination_uid, "Destination identity")
    value = f"truck:{len(origin_uid)}:{origin_uid}:{destination_uid}"
    return sha256(value.encode()).hexdigest()
