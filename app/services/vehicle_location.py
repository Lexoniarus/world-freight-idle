"""Restore persisted vehicle locations at an explicit service boundary."""

from dataclasses import dataclass

from app.domain.game import OwnedVehicle
from app.domain.ports import WorldCatalogue
from app.domain.world_scopes import WorldScope


@dataclass(frozen=True, slots=True)
class VehicleLocationResolver:
    """Restore a missing location snapshot from the world catalogue."""

    world: WorldCatalogue

    def resolve(self, vehicle: OwnedVehicle) -> None:
        """Restore the vehicle location only when persistence omitted it."""
        if vehicle.location is not None:
            return
        location = (
            WorldScope(self.world.read())
            .facility(vehicle.facility_uid)
            .location_snapshot()
        )
        vehicle.restore_location(location)
