"""Typed mutable entities for the player-owned game state."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import VehicleModel, VehicleStatus
from app.domain.validation import (
    require_finite,
    require_identity,
    require_integer,
)
from app.domain.world import FacilityLocationSnapshot


@dataclass(slots=True, init=False)
class PlayerState:
    """Player-owned economy state and its mutation invariants."""

    _cash: int
    _completed: int
    _reputation: int

    def __init__(self, cash: int, completed: int, reputation: int) -> None:
        """Initialize economy state without silently coercing values."""
        require_integer(cash, "Cash")
        require_integer(completed, "Completed deliveries")
        require_integer(reputation, "Reputation")
        self._cash = cash
        self._completed = completed
        self._reputation = reputation

    def debit(self, amount: int) -> None:
        """Debit a non-negative amount without allowing negative cash."""
        require_integer(amount, "Debit")
        if self._cash < amount:
            raise ValueError("Nicht genug Geld für die Betriebskosten.")
        self._cash -= amount

    def complete_delivery(self, payout_eur: int) -> None:
        """Credit one completed delivery and increment player progress.

        The caller ensures atomic settlement of the transport.
        """
        require_integer(payout_eur, "Payout")
        self._cash += payout_eur
        self._completed += 1
        self._reputation += 1

    def replace_cash(self, cash: int) -> None:
        """Apply explicitly requested maintenance without changing progress."""
        require_integer(cash, "Cash")
        self._cash = cash

    @property
    def cash(self) -> int:
        """Expose the current cash without a writable field."""
        return self._cash

    @property
    def completed(self) -> int:
        """Return the completed-delivery count."""
        return self._completed

    @property
    def reputation(self) -> int:
        """Expose the current reputation without a writable field."""
        return self._reputation


@dataclass(slots=True, init=False)
class OwnedVehicle:
    """Player-owned vehicle with stable identity and mutable game state."""

    _id: str
    _name: str
    _mode: str
    _capacity_tons: float
    _status: VehicleStatus
    _model_id: str | None
    _operating_cost_eur_per_km: float | None
    _facility_uid: str
    _location: FacilityLocationSnapshot | None

    def __init__(
        self,
        id: str,
        name: str,
        mode: str,
        capacity_tons: float,
        facility_uid: str,
        status: VehicleStatus,
        model_id: str | None = None,
        operating_cost_eur_per_km: float | None = None,
        location: FacilityLocationSnapshot | None = None,
    ) -> None:
        """Initialize one coherent owned-vehicle snapshot."""
        require_identity(id, "Vehicle ID")
        require_identity(name, "Vehicle name")
        require_identity(mode, "Vehicle mode")
        require_identity(facility_uid, "Facility ID")
        require_finite(capacity_tons, "Capacity", 0.01)
        if operating_cost_eur_per_km is not None:
            require_finite(operating_cost_eur_per_km, "Kilometer cost")
        if status not in {"idle", "enroute"}:
            raise ValueError("Invalid vehicle status.")
        if location is not None and location.facility_uid != facility_uid:
            raise ValueError("Vehicle location snapshot differs.")
        self._id = id
        self._name = name
        self._mode = mode
        self._capacity_tons = capacity_tons
        self._status = status
        self._model_id = model_id
        self._operating_cost_eur_per_km = operating_cost_eur_per_km
        self._facility_uid = facility_uid
        self._location = location

    def validate_dispatch(
        self,
        contract_mode: str,
        origin_facility_uid: str,
        tons: float,
    ) -> None:
        """Validate whether this vehicle can accept one contract."""
        require_finite(tons, "Tonnage", 0.01)
        if self._status != "idle":
            raise ValueError("Fahrzeug ist nicht verfügbar.")
        if self._mode != contract_mode:
            raise ValueError("Fahrzeugtyp passt nicht zum Auftrag.")
        if self._facility_uid != origin_facility_uid:
            raise ValueError("Fahrzeug steht nicht an der Abholadresse.")
        if self._capacity_tons < tons:
            raise ValueError("Fahrzeugkapazität reicht nicht aus.")

    def start_trip(self) -> None:
        """Mark the vehicle as reserved for an active transport."""
        if self._status != "idle":
            raise ValueError("Fahrzeug ist nicht verfügbar.")
        self._status = "enroute"

    def arrive(self, location: FacilityLocationSnapshot) -> None:
        """Move the vehicle to an immutable destination snapshot."""
        if self._status != "enroute":
            raise ValueError("Only a travelling vehicle can arrive.")
        self._facility_uid = location.facility_uid
        self._location = location
        self._status = "idle"

    def apply_model(self, model: VehicleModel) -> None:
        """Replace model gameplay values while retaining vehicle identity."""
        require_identity(model.id, "Model ID")
        require_identity(model.name, "Model name")
        require_identity(model.mode, "Model mode")
        require_finite(model.capacity_tons, "Capacity", 0.01)
        require_finite(model.operating_cost_eur_per_km, "Kilometer cost")
        self._model_id = model.id
        self._name = model.name
        self._mode = model.mode
        self._capacity_tons = model.capacity_tons
        self._operating_cost_eur_per_km = model.operating_cost_eur_per_km

    @property
    def id(self) -> str:
        """Expose the current id without a writable field."""
        return self._id

    @property
    def name(self) -> str:
        """Expose the current name without a writable field."""
        return self._name

    @property
    def mode(self) -> str:
        """Expose the current mode without a writable field."""
        return self._mode

    @property
    def capacity_tons(self) -> float:
        """Return the purchased payload capacity in tons."""
        return self._capacity_tons

    @property
    def status(self) -> VehicleStatus:
        """Expose the current status without a writable field."""
        return self._status

    @property
    def model_id(self) -> str | None:
        """Return the catalogue model identity, when recorded."""
        return self._model_id

    @property
    def operating_cost_eur_per_km(self) -> float | None:
        """Expose the stored kilometer cost without a writable field."""
        return self._operating_cost_eur_per_km

    @property
    def facility_uid(self) -> str:
        """Return the persistent facility identity."""
        return self._facility_uid

    @property
    def location(self) -> FacilityLocationSnapshot | None:
        """Expose the current location without a writable field."""
        return self._location
