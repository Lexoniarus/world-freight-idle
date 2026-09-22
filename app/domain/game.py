"""Typed mutable entities for the player-owned game state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.models import VehicleModel, VehicleStatus
from app.domain.world import FacilityLocationSnapshot


@dataclass(slots=True)
class PlayerState:
    """Player-owned economy state and its mutation invariants."""

    cash: int
    completed: int
    reputation: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PlayerState:
        """Hydrate one persisted player state."""
        return cls(
            cash=int(value["cash"]),
            completed=int(value["completed"]),
            reputation=int(value["reputation"]),
        )

    def to_dict(self) -> dict[str, int]:
        """Serialize the current player state for persistence or API use."""
        return {
            "cash": self.cash,
            "completed": self.completed,
            "reputation": self.reputation,
        }

    def debit(self, amount: int) -> None:
        """Debit a non-negative amount without allowing negative cash."""
        if amount < 0:
            raise ValueError("Debit must be non-negative.")
        if self.cash < amount:
            raise ValueError("Nicht genug Geld für die Betriebskosten.")
        self.cash -= amount

    def complete_delivery(self, payout_eur: int) -> None:
        """Credit one completed delivery exactly once.

        The caller owns the transaction boundary.
        """
        if payout_eur < 0:
            raise ValueError("Payout must be non-negative.")
        self.cash += payout_eur
        self.completed += 1
        self.reputation += 1


@dataclass(slots=True)
class OwnedVehicle:
    """Player-owned vehicle with stable identity and mutable game state."""

    id: str
    name: str
    mode: str
    capacity_tons: float
    hub_id: str
    status: VehicleStatus
    model_id: str | None = None
    operating_cost_eur_per_km: float | None = None
    facility_uid: str | None = None
    location: FacilityLocationSnapshot | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> OwnedVehicle:
        """Hydrate one persisted vehicle while accepting legacy snapshots."""
        raw_location = value.get("location_snapshot")
        location = (
            FacilityLocationSnapshot.from_dict(raw_location)
            if isinstance(raw_location, dict)
            else None
        )
        return cls(
            id=str(value["id"]),
            name=str(value.get("name", value["id"])),
            mode=str(value.get("mode", "truck")),
            capacity_tons=float(value.get("capacity_tons", 0.0)),
            hub_id=str(value["hub_id"]),
            status=value.get("status", "idle"),
            model_id=value.get("model_id"),
            operating_cost_eur_per_km=value.get("operating_cost_eur_per_km"),
            facility_uid=value.get("facility_uid"),
            location=location,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize without inventing optional legacy fields."""
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "model_id": self.model_id,
            "capacity_tons": self.capacity_tons,
            "hub_id": self.hub_id,
            "status": self.status,
        }
        if self.operating_cost_eur_per_km is not None:
            result["operating_cost_eur_per_km"] = (
                self.operating_cost_eur_per_km
            )
        if self.facility_uid is not None:
            result["facility_uid"] = self.facility_uid
        if self.location is not None:
            result["location_snapshot"] = self.location.to_dict()
        return result

    def validate_dispatch(
        self,
        contract_mode: str,
        origin_facility_uid: str,
        tons: float,
    ) -> None:
        """Validate whether this vehicle can accept one contract."""
        if self.status != "idle":
            raise ValueError("Fahrzeug ist nicht verfügbar.")
        if self.mode != contract_mode:
            raise ValueError("Fahrzeugtyp passt nicht zum Auftrag.")
        if self.hub_id != origin_facility_uid:
            raise ValueError("Fahrzeug steht nicht an der Abholadresse.")
        if self.capacity_tons < tons:
            raise ValueError("Fahrzeugkapazität reicht nicht aus.")

    def start_trip(self) -> None:
        """Mark the vehicle as reserved for an active transport."""
        if self.status != "idle":
            raise ValueError("Fahrzeug ist nicht verfügbar.")
        self.status = "enroute"

    def arrive(self, location: FacilityLocationSnapshot) -> None:
        """Move the vehicle to an immutable destination snapshot."""
        self.hub_id = location.facility_uid
        self.facility_uid = location.facility_uid
        self.location = location
        self.status = "idle"

    def apply_model(self, model: VehicleModel) -> None:
        """Replace model gameplay values while retaining vehicle identity."""
        self.model_id = model.id
        self.name = model.name
        self.mode = model.mode
        self.capacity_tons = model.capacity_tons
        self.operating_cost_eur_per_km = model.operating_cost_eur_per_km
