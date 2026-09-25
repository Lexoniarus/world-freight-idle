"""Vehicle reference values and ownership status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.energy import EnergyProfile
from app.domain.market_profiles import (
    TransportCapability,
    vehicle_scale_for_segment,
)
from app.domain.validation import require_finite

VehicleStatus = Literal["idle", "enroute"]


@dataclass(frozen=True, slots=True)
class VehicleImage:
    """Verified catalogue photograph with its mandatory provenance."""

    url: str
    source_url: str
    author: str
    license_name: str
    license_url: str
    attribution: str
    scope: str


@dataclass(frozen=True, slots=True)
class VehicleModel:
    """Server-owned purchase offer, separate from technical source records."""

    id: str
    name: str
    manufacturer: str
    powertrain: str
    capacity_tons: float
    price_eur: int
    operating_cost_eur_per_km: float
    maintenance_eur_per_1000_km: float
    unlock_reputation: int
    energy: EnergyProfile
    top_speed_kmh: float
    segment: str
    transport_capabilities: tuple[TransportCapability, ...]
    mode: str = "truck"
    image: VehicleImage | None = None

    def __post_init__(self) -> None:
        """Require a usable speed limit and typed energy specification."""
        require_finite(self.maintenance_eur_per_1000_km, "Maintenance")
        vehicle_scale_for_segment(self.segment)
        classes = [p.transport_class for p in self.transport_capabilities]
        if not classes or len(set(classes)) != len(classes):
            raise ValueError("Missing or duplicate transport capabilities.")
        require_finite(self.top_speed_kmh, "Top speed", 0.000001)
        if not isinstance(self.energy, EnergyProfile):
            raise ValueError("Vehicle energy profile is missing.")
