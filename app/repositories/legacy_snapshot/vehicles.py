"""Historical owned-vehicle decoding."""

from dataclasses import dataclass
from typing import Any

from app.domain.game import OwnedVehicle
from app.domain.vehicles import VehicleModel
from app.domain.world_scopes import WorldScope
from app.repositories.legacy_import_values import (
    VEHICLE_FIELDS,
    reject_unknown_fields,
)
from app.repositories.legacy_snapshot.locations import LegacyLocationReader


@dataclass(frozen=True, slots=True)
class LegacyVehicleReader:
    """Restore purchased values and canonical vehicle locations."""

    world: WorldScope
    models: dict[str, VehicleModel]
    locations: LegacyLocationReader

    def read(
        self, value: dict[str, Any], path: str = "vehicle"
    ) -> OwnedVehicle:
        """Retain purchased values and resolve the former public hub alias."""
        reject_unknown_fields(value, VEHICLE_FIELDS, path)
        uid = self.world.facility(value["hub_id"]).facility_uid
        if value.get("facility_uid", uid) != uid:
            raise ValueError("Conflicting vehicle location identities.")
        location = (
            self.locations.read(
                value["location_snapshot"], path + ".location_snapshot"
            )
            if value.get("location_snapshot") is not None
            else self.locations.read(value["hub"], path + ".hub")
            if value.get("hub") is not None
            else self.world.facility(uid).location_snapshot()
        )
        if value.get("hub") is not None:
            hub = self.locations.read(value["hub"], path + ".hub")
            if hub != location:
                raise ValueError(
                    f"Conflicting historical location at {path}.hub"
                )
        model = self.models[value["model_id"]]
        return OwnedVehicle(
            energy=model.energy,
            energy_level=model.energy.capacity,
            top_speed_kmh=model.top_speed_kmh,
            id=value["id"],
            name=value["name"],
            mode=value["mode"],
            capacity_tons=value["capacity_tons"],
            facility_uid=uid,
            status=value["status"],
            model_id=value.get("model_id"),
            operating_cost_eur_per_km=value.get("operating_cost_eur_per_km"),
            location=location,
        )
