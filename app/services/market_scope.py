"""Resolve which public facilities currently need market offers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.domain.ports import WorldCatalogue
from app.domain.world import FacilityQuery

MARKET_VIEWPORT_MIN_ZOOM = 7.0


@dataclass(frozen=True, slots=True)
class MarketScopeResolver:
    """Combine idle-truck origins with a sufficiently zoomed map viewport."""

    world: WorldCatalogue
    minimum_zoom: float = MARKET_VIEWPORT_MIN_ZOOM

    def resolve(
        self,
        vehicles: list[dict[str, Any]],
        query: FacilityQuery | None = None,
        zoom: float | None = None,
    ) -> tuple[str, ...]:
        """Return stable unique origin IDs required by the current market."""
        origins: list[str] = []
        seen: set[str] = set()

        for vehicle in vehicles:
            if vehicle.get("status") != "idle":
                continue
            identifier = vehicle.get("facility_uid") or vehicle.get("hub_id")
            if isinstance(identifier, str) and identifier not in seen:
                origins.append(identifier)
                seen.add(identifier)

        if (
            query is None
            or query.bbox is None
            or zoom is None
            or not math.isfinite(zoom)
            or zoom < self.minimum_zoom
        ):
            return tuple(origins)

        for facility in self.world.read().query(query):
            if facility.facility_uid not in seen:
                origins.append(facility.facility_uid)
                seen.add(facility.facility_uid)

        return tuple(origins)
