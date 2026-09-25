"""Immutable gameplay profiles, independent of NHM identity and storage."""

from dataclasses import dataclass
from typing import Literal

from app.domain.validation import require_finite

DistanceBand = Literal["short", "medium", "long"]
VehicleScale = Literal[
    "van", "light_distribution", "medium_distribution", "heavy"
]
DISTANCE_BANDS: tuple[DistanceBand, ...] = ("short", "medium", "long")
VEHICLE_SCALES: tuple[VehicleScale, ...] = (
    "van",
    "light_distribution",
    "medium_distribution",
    "heavy",
)
TRANSPORT_CLASSES = frozenset(
    {
        "general",
        "parcel",
        "dry_bulk",
        "liquid_bulk",
        "temperature_controlled",
        "special",
    }
)
SEGMENT_SCALES: dict[str, VehicleScale] = {
    "light_commercial_van": "van",
    "light_distribution_truck": "light_distribution",
    "medium_distribution_truck": "medium_distribution",
    "heavy_long_haul_tractor": "heavy",
}


def require_unit_weight(value: float) -> None:
    """Require a finite gameplay weight in the closed unit interval."""
    require_finite(value, "Suitability/weight")
    if value > 1:
        raise ValueError("Suitability/weight exceeds one.")


def vehicle_scale_for_segment(segment: str) -> VehicleScale:
    """Resolve only explicitly supported catalogue segments."""
    if segment not in SEGMENT_SCALES:
        raise ValueError("Unknown vehicle segment.")
    return SEGMENT_SCALES[segment]


@dataclass(frozen=True, slots=True)
class TransportCapability:
    """Gameplay suitability, not an assertion of installed equipment."""

    transport_class: str
    suitability_game: float

    def __post_init__(self) -> None:
        """Reject unknown classes and invalid suitability."""
        if self.transport_class not in TRANSPORT_CLASSES:
            raise ValueError("Unknown transport class.")
        require_unit_weight(self.suitability_game)


@dataclass(frozen=True, slots=True)
class DistanceLoadProfile:
    """Selection weight and shipment load interval for a distance band."""

    distance_band: DistanceBand
    selection_weight: float
    load_factor_min: float
    load_factor_max: float

    def __post_init__(self) -> None:
        """Require a supported band and a positive ordered load interval."""
        if self.distance_band not in DISTANCE_BANDS:
            raise ValueError("Unknown distance band.")
        require_unit_weight(self.selection_weight)
        require_unit_weight(self.load_factor_min)
        require_unit_weight(self.load_factor_max)
        if not 0 < self.load_factor_min <= self.load_factor_max:
            raise ValueError("Invalid load factor interval.")


@dataclass(frozen=True, slots=True)
class VehicleScaleProfile:
    """NHM-specific suitability of one explicit vehicle scale."""

    vehicle_scale: VehicleScale
    suitability_game: float

    def __post_init__(self) -> None:
        """Reject unsupported scales and invalid suitability."""
        if self.vehicle_scale not in VEHICLE_SCALES:
            raise ValueError("Unknown vehicle scale.")
        require_unit_weight(self.suitability_game)


@dataclass(frozen=True, slots=True)
class NhmMarketProfile:
    """Complete immutable market behavior of one operational NHM node."""

    nhm_row_id: int
    transport_class: str
    value_eur_per_t: float
    freight_rate_factor_game: float
    distance_profiles: tuple[DistanceLoadProfile, ...]
    scale_profiles: tuple[VehicleScaleProfile, ...]

    def __post_init__(self) -> None:
        """Require complete, unique profiles and positive economic terms."""
        if self.transport_class not in TRANSPORT_CLASSES:
            raise ValueError("Unknown transport class.")
        for value in (self.value_eur_per_t, self.freight_rate_factor_game):
            require_finite(value, "Market value")
            if value == 0:
                raise ValueError("Market value must be positive.")
        if len(self.distance_profiles) != len(DISTANCE_BANDS) or {
            p.distance_band for p in self.distance_profiles
        } != set(DISTANCE_BANDS):
            raise ValueError("Incomplete distance profiles.")
        if len(self.scale_profiles) != len(VEHICLE_SCALES) or {
            p.vehicle_scale for p in self.scale_profiles
        } != set(VEHICLE_SCALES):
            raise ValueError("Incomplete vehicle scale profiles.")
