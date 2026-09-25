"""Immutable simulation cost terms and exact energy purchase accounting."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.domain.energy import EnergyKind, EnergyUnit
from app.domain.journeys import JourneyPlan
from app.domain.validation import require_finite, require_integer

COST_POLICY_VERSION = "maintenance-energy-v1"
ENERGY_PRICES = {
    "diesel": Decimal("1.50"),
    "gas": Decimal("1.20"),
    "electric": Decimal("0.30"),
}
BASE_COST_EUR = 80


def whole_euros(value: Decimal) -> int:
    """Round one monetary component to whole simulation euros."""
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True, slots=True)
class VehicleCostProfile:
    """Explicit reference maintenance, separate from aggregate legacy costs."""

    maintenance_eur_per_km: float

    def __post_init__(self) -> None:
        """Reject missing, negative and nonfinite maintenance rates."""
        require_finite(self.maintenance_eur_per_km, "Maintenance rate")


@dataclass(frozen=True, slots=True)
class EnergyPurchase:
    """One planned purchase, with its journey segment and exact charge."""

    segment_index: int
    quantity: float
    cost_eur: int

    def __post_init__(self) -> None:
        """Require a positive purchase and whole nonnegative charge."""
        require_integer(self.segment_index, "Segment index")
        require_finite(self.quantity, "Energy purchase", 0.000001)
        require_integer(self.cost_eur, "Energy charge")


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Stored dispatch costs; historical trips may have no breakdown."""

    policy_version: str
    maintenance_eur_per_km: float
    energy_kind: EnergyKind
    energy_unit: EnergyUnit
    energy_price_eur_per_unit: float
    base_cost_eur: int
    maintenance_cost_eur: int
    purchases: tuple[EnergyPurchase, ...]
    energy_cost_eur: int
    total_cost_eur: int

    def __post_init__(self) -> None:
        """Require consistent stored components without live price lookup."""
        if not self.policy_version:
            raise ValueError("Cost policy version is missing.")
        VehicleCostProfile(self.maintenance_eur_per_km)
        require_finite(self.energy_price_eur_per_unit, "Energy price", 0.01)
        if {"diesel": "l", "gas": "kg", "electric": "kWh"}.get(
            self.energy_kind
        ) != self.energy_unit:
            raise ValueError("Cost energy unit differs.")
        for amount in (
            self.base_cost_eur,
            self.maintenance_cost_eur,
            self.energy_cost_eur,
            self.total_cost_eur,
        ):
            require_integer(amount, "Cost component")
        if (
            not isinstance(self.purchases, tuple)
            or self.energy_cost_eur != sum(p.cost_eur for p in self.purchases)
            or self.total_cost_eur
            != self.base_cost_eur
            + self.maintenance_cost_eur
            + self.energy_cost_eur
        ):
            raise ValueError("Cost components do not reconcile.")


def journey_costs(
    journey: JourneyPlan, profile: VehicleCostProfile
) -> CostBreakdown:
    """Charge actual purchases and maintenance over the complete journey."""
    if journey.energy is None:
        raise ValueError("New dispatch requires metered energy.")
    energy = journey.energy
    unit_price = ENERGY_PRICES[energy.kind]
    purchases = tuple(
        EnergyPurchase(
            index, float(quantity), whole_euros(quantity * unit_price)
        )
        for index, segment in enumerate(journey.segments)
        if segment.phase != "driving"
        and segment.start_energy is not None
        and segment.end_energy is not None
        and (
            quantity := Decimal(str(segment.end_energy))
            - Decimal(str(segment.start_energy))
        )
        > 0
    )
    maintenance = whole_euros(
        Decimal(str(journey.distance_km))
        * Decimal(str(profile.maintenance_eur_per_km))
    )
    energy_cost = sum(p.cost_eur for p in purchases)
    return CostBreakdown(
        COST_POLICY_VERSION,
        profile.maintenance_eur_per_km,
        energy.kind,
        energy.unit,
        float(unit_price),
        BASE_COST_EUR,
        maintenance,
        purchases,
        energy_cost,
        BASE_COST_EUR + maintenance + energy_cost,
    )
