"""Bidirectional connection evidence and stable publication identities."""

from dataclasses import dataclass
from hashlib import sha256

from app.domain.routes import RouteSnapshot
from app.domain.routing_anchors import VALIDATION_VERSION, RoutingAnchor
from app.domain.routing_readiness import relation_identity


@dataclass(frozen=True, slots=True)
class ValidatedConnection:
    """Both actual road geometries for a single pair of certified accesses."""

    origin: RoutingAnchor
    destination: RoutingAnchor
    forward: RouteSnapshot
    reverse: RouteSnapshot


def connection_identity(origin: str, destination: str) -> str:
    """Share a lease and proof across simultaneous opposite requests."""
    first, second = sorted((origin, destination))
    return "connection:" + relation_identity(first, second)


def connection_leases(origin: str, destination: str) -> tuple[str, ...]:
    """Acquire every shared resource in the same order without waiting."""
    return tuple(
        sorted(
            {
                connection_identity(origin, destination),
                f"anchor:{origin}:truck",
                f"anchor:{destination}:truck",
                relation_identity(origin, destination),
                relation_identity(destination, origin),
            }
        )
    )


def anchor_identity(anchor: RoutingAnchor | None) -> str:
    """Ignore refresh timestamps while retaining all route-relevant facts."""
    facts = (
        None
        if anchor is None
        else (
            (float(anchor.anchor.latitude), float(anchor.anchor.longitude))
            if anchor.anchor
            else None,
            (
                float(anchor.facility_coordinates.latitude),
                float(anchor.facility_coordinates.longitude),
            )
            if anchor.facility_coordinates
            else None,
            anchor.validation_status,
            anchor.provider,
            anchor.provider_revision,
            anchor.source_fingerprint,
        )
    )
    return sha256(repr((VALIDATION_VERSION, facts)).encode()).hexdigest()
