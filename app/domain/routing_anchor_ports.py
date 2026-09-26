"""Ports for derived facility routing anchors."""

from __future__ import annotations

from typing import Protocol

from app.domain.geography import Coordinates
from app.domain.routing_anchors import LocateResult, RoutingAnchor
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


class TruckAnchorLocator(Protocol):
    """Validate one coordinate against a real truck-routing graph."""

    async def locate(self, coordinates: Coordinates) -> LocateResult:
        """Return the correlated truck-routing position."""
        ...


class RoutingAnchorResolverPort(Protocol):
    """Resolve one facility identity to derived routing coordinates."""

    async def resolve(self, facility: Facility) -> RoutingAnchor:
        """Resolve or reuse one routing anchor."""
        ...
