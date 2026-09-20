"""Map projection of public catalogue facilities, without geocoding."""

from typing import Any

from app.domain.ports import WorldCatalogue
from app.domain.world import FacilityQuery


class MapLocationService:
    """Filter immutable world data without touching player-owned depots."""

    def __init__(self, world: WorldCatalogue) -> None:
        self.world = world

    def list_facilities(self, query: FacilityQuery) -> dict[str, Any]:
        """Return bounded endpoints and explicit unavailable counts."""
        snapshot = self.world.read()
        return {
            "facilities": [
                facility.location_snapshot()
                for facility in snapshot.query(query)
            ],
            "catalogue_version": snapshot.version,
            "unavailable_count": sum(
                not f.is_routable() for f in snapshot.facilities
            ),
        }

    async def list_hubs(self) -> list[dict[str, Any]]:
        """Keep the v1 envelope while all IDs now denote facilities."""
        return self.list_facilities(FacilityQuery())["facilities"]
