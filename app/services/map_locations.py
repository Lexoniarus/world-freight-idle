"""Query public catalogue locations without HTTP or geocoding knowledge."""

from app.domain.ports import WorldCatalogue
from app.domain.results import FacilityPage
from app.domain.world import FacilityQuery


class MapLocationService:
    """Filter immutable world data without touching player-owned depots."""

    def __init__(self, world: WorldCatalogue) -> None:
        self.world = world

    def list_facilities(self, query: FacilityQuery) -> FacilityPage:
        """Return bounded endpoint values and catalogue availability."""
        snapshot = self.world.read()
        return FacilityPage(
            tuple(
                facility.location_snapshot()
                for facility in snapshot.query(query)
            ),
            snapshot.version,
            sum(
                not facility.is_routable() for facility in snapshot.facilities
            ),
        )
