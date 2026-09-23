"""Immutable vehicle energy measurements and consumption rules."""

from dataclasses import dataclass
from typing import Literal

from app.domain.validation import require_finite

EnergyKind = Literal["diesel", "gas", "electric"]
EnergyUnit = Literal["l", "kg", "kWh"]


@dataclass(frozen=True, slots=True)
class EnergyProfile:
    """Purchased energy specification, independent of catalogue updates."""

    kind: EnergyKind
    unit: EnergyUnit
    capacity: float
    consumption_per_100km: float
    stop_minutes: float
    reserve_fraction: float

    def __post_init__(self) -> None:
        """Reject inconsistent units and unusable consumption profiles."""
        units = {"diesel": "l", "gas": "kg", "electric": "kWh"}
        if self.kind not in units or self.unit != units[self.kind]:
            raise ValueError("Energy kind and unit differ.")
        require_finite(self.capacity, "Energy capacity", 0.000001)
        require_finite(self.consumption_per_100km, "Consumption", 0.000001)
        require_finite(self.stop_minutes, "Energy stop", 0.000001)
        require_finite(self.reserve_fraction, "Energy reserve", 0.000001)
        if self.reserve_fraction >= 1:
            raise ValueError("Energy reserve must be below capacity.")

    def validate_level(self, level: float) -> None:
        """Require a physically possible stored quantity."""
        require_finite(level, "Energy level")
        if level > self.capacity:
            raise ValueError("Energy level exceeds capacity.")

    def consumption_for(self, distance_km: float) -> float:
        """Calculate consumption from travelled provider kilometres."""
        require_finite(distance_km, "Travelled distance")
        return distance_km * self.consumption_per_100km / 100
