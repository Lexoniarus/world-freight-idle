"""Immutable trade relations, candidates and city coverage plans."""

from dataclasses import dataclass

from app.domain.cargo import FacilityNhmProfile, NhmProduct
from app.domain.economics import VehicleCostProfile
from app.domain.energy import EnergyProfile
from app.domain.market_profiles import (
    VEHICLE_SCALES,
    DistanceLoadProfile,
    NhmMarketProfile,
    TransportCapability,
    VehicleScale,
    require_unit_weight,
)
from app.domain.validation import require_finite, require_identity
from app.domain.world import Facility


@dataclass(frozen=True, slots=True)
class TradeOption:
    """One NHM-compatible relation without vehicle or market decisions."""

    origin: Facility
    origin_cargo: FacilityNhmProfile
    destination: Facility
    destination_cargo: FacilityNhmProfile
    cargo: NhmProduct
    match_type: str


@dataclass(frozen=True, slots=True)
class MarketVehicle:
    """Immutable generation facts resolved from an idle owned vehicle."""

    vehicle_id: str
    model_id: str
    city_uid: str
    mode: str
    capacity_tons: float
    scale: VehicleScale
    capabilities: tuple[TransportCapability, ...]
    cost_profile: VehicleCostProfile
    energy: EnergyProfile

    def __post_init__(self) -> None:
        """Require explicit identity, scale and usable owned capacity."""
        for value in (
            self.vehicle_id,
            self.model_id,
            self.city_uid,
            self.mode,
        ):
            require_identity(value, "Market vehicle identity")
        require_finite(self.capacity_tons, "Owned capacity", 0.01)
        if self.scale not in VEHICLE_SCALES:
            raise ValueError("Unknown market vehicle scale.")


@dataclass(frozen=True, slots=True)
class CompatibleVehicle:
    """One compatible vehicle and its independent selection weight."""

    vehicle: MarketVehicle
    suitability: float

    def __post_init__(self) -> None:
        """Require a strictly positive selectable vehicle weight."""
        require_unit_weight(self.suitability)
        if self.suitability == 0:
            raise ValueError("Compatible vehicle needs positive suitability.")


@dataclass(frozen=True, slots=True)
class MarketCandidate:
    """A feasible trade, still without concrete shipment or offer identity."""

    trade: TradeOption
    profile: NhmMarketProfile
    distance_profile: DistanceLoadProfile
    estimated_distance_km: float
    vehicles: tuple[CompatibleVehicle, ...]
    weight: float
    reference_nhm_factor: float

    def __post_init__(self) -> None:
        """Require coherent market facts and a selectable vehicle pool."""
        require_finite(self.estimated_distance_km, "Estimated distance")
        require_finite(self.weight, "Candidate weight")
        require_finite(
            self.reference_nhm_factor, "Reference NHM factor", 0.000001
        )
        if not self.vehicles or self.weight == 0:
            raise ValueError("Candidate requires positive selectable context.")
        if (
            self.profile.nhm_row_id != self.trade.cargo.nhm_row_id
            or self.distance_profile not in self.profile.distance_profiles
            or any(
                v.vehicle.city_uid != self.trade.origin.address.city.city_uid
                for v in self.vehicles
            )
        ):
            raise ValueError("Candidate context differs from its trade.")


@dataclass(frozen=True, slots=True)
class CoverageDiagnostic:
    """Compact coverage counts for one active city."""

    city_uid: str
    eligible_facilities: int
    covered_facilities: int
    distance_counts: tuple[int, int, int]
    unmet_bands: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CoveragePlan:
    """Selected candidates and expected coverage, without materialization."""

    selected: tuple[MarketCandidate, ...]
    diagnostics: tuple[CoverageDiagnostic, ...]
