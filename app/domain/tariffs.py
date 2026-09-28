"""Immutable NHM minimum freight, independent of shipment selection."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.economics import ENERGY_PRICES, VehicleCostProfile
from app.domain.energy import EnergyProfile
from app.domain.validation import require_finite

TARIFF_VERSION = "nhm-minimum-v1"
REFERENCE_MARGIN = Decimal("0.20")


@dataclass(frozen=True, slots=True)
class FreightTariff:
    """Generation-time rate inputs retained for every later vehicle choice."""

    version: str
    nhm_factor: float
    reference_nhm_factor: float
    reference_cost_eur_per_km: float
    minimum_eur_per_km: float

    def __post_init__(self) -> None:
        """Reject incomplete and nonpositive stored tariff facts."""
        if not self.version:
            raise ValueError("Tariff version is missing.")
        for value in (
            self.nhm_factor,
            self.reference_nhm_factor,
            self.reference_cost_eur_per_km,
            self.minimum_eur_per_km,
        ):
            require_finite(value, "Tariff term", 0.000001)


def freight_tariff(
    cost: VehicleCostProfile,
    energy: EnergyProfile,
    nhm_factor: float,
    reference_factor: float,
) -> FreightTariff:
    """Derive NHM minimum freight from the generation vehicle context."""
    require_finite(nhm_factor, "NHM factor", 0.000001)
    require_finite(reference_factor, "Reference NHM factor", 0.000001)
    reference_cost = Decimal(str(cost.maintenance_eur_per_km)) + (
        Decimal(str(energy.consumption_per_100km))
        / 100
        * ENERGY_PRICES[energy.kind]
    )
    minimum = (
        reference_cost
        / (1 - REFERENCE_MARGIN)
        * (Decimal(str(nhm_factor)) / Decimal(str(reference_factor)))
    )
    return FreightTariff(
        TARIFF_VERSION,
        nhm_factor,
        reference_factor,
        float(reference_cost),
        float(minimum),
    )
