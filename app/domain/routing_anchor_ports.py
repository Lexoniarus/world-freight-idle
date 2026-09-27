"""Ports for derived facility routing anchors."""

from __future__ import annotations

from typing import Protocol

from app.domain.geography import Coordinates
from app.domain.routing_anchors import (
    LocateResult,
    RoutingAnchor,
    RoutingCandidate,
)
from app.domain.world import Facility


class RoutingAnchorStore(Protocol):
    """Persist global derived routing anchors outside catalogue entities."""

    def get(
        self,
        facility_uid: str,
        routing_profile: str,
    ) -> RoutingAnchor | None:
        """Return one persisted routing result."""
        ...

    def put(self, anchor: RoutingAnchor) -> None:
        """Replace one persisted routing result."""
        ...

    def put_leased(
        self, anchor: RoutingAnchor, owner: str, now: float
    ) -> bool:
        """Persist only while the matching global anchor lease is owned."""
        ...


class TruckAnchorLocator(Protocol):
    """Find candidate correlations on a real truck-routing graph."""

    async def locate(self, coordinates: Coordinates) -> LocateResult:
        """Return real road candidates without certifying connectivity."""
        ...


class RoutingAnchorResolverPort(Protocol):
    """Resolve one facility identity to derived routing coordinates."""

    max_snap_distance_m: float

    async def resolve(
        self, facility: Facility, *, force: bool = False
    ) -> tuple[RoutingCandidate, ...]:
        """Find bounded candidates; force also explores the postal address."""
        ...
