"""Explicit profile maintenance without CLI or SQL dependencies."""

import logging
from collections.abc import Callable
from typing import Any

from app.domain.game import OwnedVehicle, PlayerState
from app.domain.models import VehicleModel
from app.domain.ports import VehicleCatalogue
from app.repositories.accounts import AccountRepository
from app.repositories.sqlite_store import SqliteStore

LOGGER = logging.getLogger(__name__)


class ProfileMaintenanceService:
    """Update selected model snapshots inside one player transaction."""

    def __init__(
        self,
        catalogue: VehicleCatalogue,
        accounts: AccountRepository,
        player_store_factory: Callable[[str], SqliteStore],
    ) -> None:
        self.catalogue = catalogue
        self.accounts = accounts
        self.player_store_factory = player_store_factory

    def update_profile(
        self,
        username: str,
        assignments: dict[str, str],
        cash: int | None = None,
    ) -> dict[str, Any]:
        """Apply an explicit request; preserve unselected and trip values."""
        if cash is not None and (type(cash) is not int or cash < 0):
            raise ValueError("Cash must be a non-negative integer")
        user = self.accounts.find_user(username)
        if user is None:
            raise ValueError("Unknown profile")
        models = {model.id: model for model in self.catalogue.list_models()}
        store = self.player_store_factory(user["id"])
        with store.transaction():
            raw_player = store.get_json("player")
            raw_vehicles = store.get_json("vehicles")
            if raw_player is None or raw_vehicles is None:
                raise ValueError("Profile has no initialized game state")
            player = PlayerState.from_dict(raw_player)
            vehicles = [OwnedVehicle.from_dict(item) for item in raw_vehicles]
            validate_assignments(vehicles, assignments, models)
            trips = store.get_json("active_trips", [])
            for vehicle in vehicles:
                if vehicle.id not in assignments:
                    continue
                model = models[assignments[vehicle.id]]
                validate_active_load(vehicle.id, model, trips)
                vehicle.apply_model(model)
            if cash is not None:
                player.cash = cash
            store.set_json("vehicles", [item.to_dict() for item in vehicles])
            store.set_json("player", player.to_dict())
        LOGGER.info(
            "Profile maintenance completed",
            extra={
                "event": "profile.maintenance",
                "data": {
                    "user_id": user["id"],
                    "vehicle_count": len(assignments),
                    "cash_changed": cash is not None,
                },
            },
        )
        return {
            "username": user["username"],
            "cash": player.cash,
            "assignments": assignments,
        }


def validate_assignments(
    vehicles: list[OwnedVehicle],
    assignments: dict[str, str],
    models: dict[str, VehicleModel],
) -> None:
    """Reject empty requests or identifiers outside the selected profile."""
    known = {vehicle.id for vehicle in vehicles}
    if (
        not assignments
        or not assignments.keys() <= known
        or not set(assignments.values()) <= models.keys()
    ):
        raise ValueError("Unknown vehicle or model, or empty assignment")


def validate_active_load(
    vehicle_id: str, model: VehicleModel, trips: list[dict[str, Any]]
) -> None:
    """Require the replacement model to carry every existing active load."""
    if any(
        trip["vehicle_id"] == vehicle_id
        and float(trip["contract"]["tons"]) > model.capacity_tons
        for trip in trips
    ):
        raise ValueError("New vehicle cannot carry its active load")
