"""Query public catalogue locations without HTTP or geocoding knowledge."""

from app.domain.geography import City
from app.domain.ports import WorldCatalogue
from app.domain.results import FacilityPage
from app.domain.world import FacilityLocationSnapshot, FacilityQuery
from app.domain.world_scopes import WorldScope


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
                for facility in WorldScope(snapshot).query(query)
            ),
            snapshot.version,
            sum(
                not facility.is_routable() for facility in snapshot.facilities
            ),
        )

    def exact_facility(self, identifier: str) -> FacilityLocationSnapshot:
        """Resolve one UID or maintained alias without listing the world."""
        return (
            WorldScope(self.world.read())
            .facility(identifier)
            .location_snapshot()
        )

    def exact_city(self, city_uid: str) -> City:
        """Require a stable city UID, never a potentially ambiguous name."""
        city = WorldScope(self.world.read()).city(city_uid).city
        if city.city_uid != city_uid:
            raise KeyError("Stadt-ID nicht gefunden")
        return city
