"""Immutable generation terms retained independently of live catalogues."""

from dataclasses import dataclass

from app.domain.market_calculations import distance_band
from app.domain.market_profiles import (
    TRANSPORT_CLASSES,
    VEHICLE_SCALES,
    DistanceBand,
    VehicleScale,
)
from app.domain.validation import require_finite, require_integer


@dataclass(frozen=True, slots=True)
class OfferMarketContext:
    """V2 provenance of a shipment; never an exclusive vehicle reservation."""

    distance_band: DistanceBand
    estimated_distance_km: float
    transport_class: str
    generated_for_vehicle_scale: VehicleScale
    generated_capacity_tons: float
    cargo_value_eur_per_t: float
    cargo_value_eur: int

    def __post_init__(self) -> None:
        """Reject inconsistent distance, equipment and monetary facts."""
        if self.distance_band != distance_band(self.estimated_distance_km):
            raise ValueError("Distance band differs from estimate.")
        if self.transport_class not in TRANSPORT_CLASSES:
            raise ValueError("Unknown transport class.")
        if self.generated_for_vehicle_scale not in VEHICLE_SCALES:
            raise ValueError("Unknown vehicle scale.")
        require_finite(self.generated_capacity_tons, "Capacity", 0.01)
        require_finite(self.cargo_value_eur_per_t, "Cargo value", 0.000001)
        require_integer(self.cargo_value_eur, "Cargo value")

    def validate_tonnage(self, tons: float) -> None:
        """Require shipment capacity and rounded cargo value consistency."""
        if (
            tons > self.generated_capacity_tons
            or round(tons * self.cargo_value_eur_per_t) != self.cargo_value_eur
        ):
            raise ValueError("Shipment differs from generation context.")
