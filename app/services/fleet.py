"""Vehicle catalogue and atomic fleet purchases."""

import logging
import uuid

from app.domain.errors import CatalogueError, WorldCatalogueError
from app.domain.models import VehicleModel
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.repositories.sqlite_store import SqliteStore

LOGGER = logging.getLogger(__name__)


class FleetService:
    """Buy vehicles using server-owned prices and a fixed delivery hub."""

    def __init__(
        self,
        store: SqliteStore,
        catalogue: VehicleCatalogue,
        world: WorldCatalogue,
    ) -> None:
        self.store = store
        self.catalogue = catalogue
        self.world = world

    def list_catalogue(self) -> dict:
        """Return server-owned purchase offers and their delivery hub."""
        return {
            "models": [
                model.to_dict() for model in self.catalogue.list_models()
            ],
            "delivery_hub": resolve_delivery_facility(self.world)["label"],
        }

    def purchase(self, model_id: str) -> dict:
        """Debit cash and add one vehicle in the same database transaction."""
        model = next(
            (
                item
                for item in self.catalogue.list_models()
                if item.id == model_id
            ),
            None,
        )
        if model is None:
            raise ValueError("Unbekanntes Fahrzeugmodell.")
        location = resolve_delivery_facility(self.world)
        with self.store.transaction():
            player = self.store.get_json("player")
            if player["reputation"] < model.unlock_reputation:
                raise ValueError(
                    "Deine Reputation reicht für dieses Modell nicht aus."
                )
            if player["cash"] < model.price_eur:
                raise ValueError("Nicht genug Geld für dieses Fahrzeug.")
            vehicles = self.store.get_json("vehicles")
            vehicle = build_vehicle_snapshot(model, uuid.uuid4().hex, location)
            player["cash"] -= model.price_eur
            vehicles.append(vehicle)
            self.store.set_json("player", player)
            self.store.set_json("vehicles", vehicles)
        LOGGER.info(
            "Vehicle purchased",
            extra={
                "event": "fleet.purchase",
                "data": {"vehicle_id": vehicle["id"], "model_id": model_id},
            },
        )
        return vehicle


def build_vehicle_snapshot(
    model: VehicleModel,
    vehicle_id: str,
    location: dict,
) -> dict:
    """Snapshot gameplay values for one owned vehicle at the delivery hub."""
    return {
        "id": vehicle_id,
        "name": model.name,
        "mode": model.mode,
        "model_id": model.id,
        "operating_cost_eur_per_km": model.operating_cost_eur_per_km,
        "capacity_tons": model.capacity_tons,
        "hub_id": location["facility_uid"],
        "facility_uid": location["facility_uid"],
        "location_snapshot": location,
        "status": "idle",
    }


def create_starter_vehicle(
    catalogue: VehicleCatalogue, location: dict
) -> dict:
    """Grant the catalogue IVECO without debiting the starting balance."""
    for model in catalogue.list_models():
        if model.id == "iveco_sway_500":
            return build_vehicle_snapshot(model, "truck_01", location)
    LOGGER.error(
        "Starter vehicle missing from catalogue",
        extra={"event": "catalogue.starter_missing"},
    )
    raise CatalogueError("Startfahrzeug derzeit nicht verfügbar.")


def resolve_delivery_facility(world: WorldCatalogue) -> dict:
    """Require the reviewed start endpoint before creating a vehicle."""
    try:
        facility = world.read().get_facility("berlin_westhafen")
        if not facility.is_routable():
            raise ValueError("Unverified delivery facility")
    except (KeyError, ValueError) as exc:
        LOGGER.error(
            "Delivery facility unavailable",
            extra={
                "event": "world.delivery_unavailable",
            },
        )
        raise WorldCatalogueError("Startstandort nicht verfügbar.") from exc
    return facility.to_dict()
