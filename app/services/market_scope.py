"""Resolve active city identities exclusively from owned idle vehicles."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.game import OwnedVehicle
from app.domain.ports import WorldCatalogue
from app.domain.world_scopes import WorldScope


@dataclass(frozen=True, slots=True)
class MarketScopeResolver:
    """Resolve saved vehicle locations, never viewport state."""

    world: WorldCatalogue

    def resolve(self, vehicles: Sequence[OwnedVehicle]) -> tuple[str, ...]:
        """Return stable distinct city UIDs even for multiple idle trucks."""
        cities = set()
        for vehicle in vehicles:
            if vehicle.status != "idle":
                continue
            location = vehicle.location
            if location is None:
                location = (
                    WorldScope(self.world.read())
                    .facility(vehicle.facility_uid)
                    .location_snapshot()
                )
            cities.add(location.city.city_uid)
        return tuple(sorted(cities))
