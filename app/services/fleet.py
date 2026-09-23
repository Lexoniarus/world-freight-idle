"""Vehicle catalogue and atomic fleet purchases."""

import logging
import uuid

from app.domain.errors import CatalogueError, WorldCatalogueError
from app.domain.game import OwnedVehicle
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.results import FleetCatalogue
from app.domain.state_ports import GameUnitOfWork
from app.domain.vehicles import VehicleModel
from app.domain.world import FacilityLocationSnapshot
from app.domain.world_scopes import WorldScope

LOGGER = logging.getLogger(__name__)


class FleetService:
    """Buy vehicles using server-owned prices and a fixed delivery hub."""

    def __init__(
        self,
        unit_of_work: GameUnitOfWork,
        catalogue: VehicleCatalogue,
        world: WorldCatalogue,
    ) -> None:
        self.unit_of_work = unit_of_work
        self.state_repository = unit_of_work.repository
        self.catalogue = catalogue
        self.world = world

    def list_catalogue(self) -> FleetCatalogue:
        """Read immutable purchase choices and the fixed delivery location."""
        return FleetCatalogue(
            self.catalogue.list_models(), resolve_delivery_facility(self.world)
        )

    def purchase(self, model_id: str) -> OwnedVehicle:
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
        with self.unit_of_work.transaction():
            player = self.state_repository.get_player()
            if player is None:
                raise ValueError("Spielstand ist nicht initialisiert.")
            if player.reputation < model.unlock_reputation:
                raise ValueError(
                    "Deine Reputation reicht für dieses Modell nicht aus."
                )
            if player.cash < model.price_eur:
                raise ValueError("Nicht genug Geld für dieses Fahrzeug.")
            vehicle = build_owned_vehicle(
                model,
                uuid.uuid4().hex,
                location,
            )
            player.debit(model.price_eur)
            self.state_repository.save_player(player)
            self.state_repository.save_vehicle(vehicle)
        LOGGER.info(
            "Vehicle purchased",
            extra={
                "event": "fleet.purchase",
                "data": {"vehicle_id": vehicle.id, "model_id": model_id},
            },
        )
        return vehicle


def build_owned_vehicle(
    model: VehicleModel,
    vehicle_id: str,
    location: FacilityLocationSnapshot,
) -> OwnedVehicle:
    """Create one typed owned vehicle from immutable catalogue values."""
    return OwnedVehicle(
        id=vehicle_id,
        name=model.name,
        mode=model.mode,
        model_id=model.id,
        operating_cost_eur_per_km=model.operating_cost_eur_per_km,
        capacity_tons=model.capacity_tons,
        facility_uid=location.facility_uid,
        location=location,
        status="idle",
    )


def create_starter_vehicle(
    catalogue: VehicleCatalogue,
    location: FacilityLocationSnapshot,
) -> OwnedVehicle:
    """Grant the catalogue IVECO without debiting the starting balance."""
    for model in catalogue.list_models():
        if model.id == "iveco_sway_500":
            return build_owned_vehicle(model, "truck_01", location)
    LOGGER.error(
        "Starter vehicle missing from catalogue",
        extra={"event": "catalogue.starter_missing"},
    )
    raise CatalogueError("Startfahrzeug derzeit nicht verfügbar.")


def resolve_delivery_facility(
    world: WorldCatalogue,
) -> FacilityLocationSnapshot:
    """Require the reviewed start endpoint before creating a vehicle."""
    try:
        facility = WorldScope(world.read()).facility("berlin_westhafen")
        if not facility.is_routable():
            raise ValueError("Unroutable delivery facility")
    except (KeyError, ValueError) as exc:
        LOGGER.error(
            "Delivery facility unavailable",
            extra={
                "event": "world.delivery_unavailable",
            },
        )
        raise WorldCatalogueError("Startstandort nicht verfügbar.") from exc
    return facility.location_snapshot()
