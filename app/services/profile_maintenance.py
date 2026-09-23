"""Explicit profile maintenance without CLI or SQL dependencies."""

import logging
from collections.abc import Callable
from typing import Any

from app.domain.account_ports import AccountStore
from app.domain.game import OwnedVehicle
from app.domain.ports import VehicleCatalogue
from app.domain.state_ports import GameUnitOfWork
from app.domain.transports import ActiveTransport
from app.domain.vehicles import VehicleModel

LOGGER = logging.getLogger(__name__)


class ProfileMaintenanceService:
    """Update selected model snapshots inside one player transaction."""

    def __init__(
        self,
        catalogue: VehicleCatalogue,
        accounts: AccountStore,
        player_unit_of_work_factory: Callable[[str], GameUnitOfWork],
    ) -> None:
        self.catalogue = catalogue
        self.accounts = accounts
        self.player_unit_of_work_factory = player_unit_of_work_factory

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
        unit = self.player_unit_of_work_factory(user["id"])
        repository = unit.repository
        with unit.transaction():
            player = repository.get_player()
            vehicles = repository.list_vehicles()
            if player is None or not vehicles:
                raise ValueError("Profile has no initialized game state")
            validate_assignments(list(vehicles), assignments, models)
            trips = tuple(
                trip
                for trip in repository.list_transports()
                if trip.status == "active"
            )
            for vehicle in vehicles:
                if vehicle.id not in assignments:
                    continue
                model = models[assignments[vehicle.id]]
                validate_active_load(vehicle.id, model, trips)
                vehicle.apply_model(model)
            if cash is not None:
                player.replace_cash(cash)
            for vehicle in vehicles:
                repository.save_vehicle(vehicle)
            repository.save_player(player)
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
    vehicle_id: str, model: VehicleModel, trips: tuple[ActiveTransport, ...]
) -> None:
    """Require the replacement model to carry every existing active load."""
    if any(
        trip.vehicle_id == vehicle_id
        and trip.contract.tons > model.capacity_tons
        for trip in trips
    ):
        raise ValueError("New vehicle cannot carry its active load")
