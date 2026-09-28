"""Generate reproducible economy scenarios from injected catalogues."""

from random import Random

from app.domain.economics import VehicleCostProfile
from app.domain.economy_audit import (
    EconomyAuditSummary,
    EconomyMatrixRow,
    audit_economy_case,
)
from app.domain.market import MarketVehicle
from app.domain.market_compatibility import vehicle_suitability
from app.domain.market_profiles import (
    DistanceLoadProfile,
    NhmMarketProfile,
    vehicle_scale_for_segment,
)
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.vehicles import VehicleModel


class EconomyAuditService:
    """Own scenario enumeration without concrete persistence or output."""

    def __init__(
        self,
        vehicles: VehicleCatalogue,
        world: WorldCatalogue,
        rng: Random,
    ) -> None:
        """Inject read-only catalogue ports and deterministic randomness."""
        self.vehicles = vehicles
        self.world = world
        self.rng = rng

    def matrix(self) -> tuple[EconomyMatrixRow, ...]:
        """Enumerate unchanged low, generated median and high scenarios."""
        models = self.vehicles.list_models()
        world = self.world.read()
        reference = min(
            p.freight_rate_factor_game for p in world.market_profiles
        )
        return tuple(
            row
            for model in models
            for profile in world.market_profiles
            for load in profile.distance_profiles
            for row in self._rows(
                audit_vehicle(model), profile, load, reference
            )
        )

    def _rows(
        self,
        vehicle: MarketVehicle,
        profile: NhmMarketProfile,
        load: DistanceLoadProfile,
        reference: float,
    ) -> tuple[EconomyMatrixRow, ...]:
        """Enumerate compatibility and unchanged scenarios for one profile."""
        identity = (
            vehicle.model_id,
            vehicle.scale,
            profile.nhm_row_id,
            load.distance_band,
            load.load_factor_min,
            load.load_factor_max,
        )
        if (
            vehicle_suitability(vehicle, profile) <= 0
            or load.selection_weight <= 0
        ):
            return (EconomyMatrixRow(*identity, False),)
        typical = sorted(self.rng.random() for _ in range(101))[50]
        distances = {"short": 75, "medium": 375, "long": 1000}
        return tuple(
            EconomyMatrixRow(
                *identity,
                True,
                label,
                approach,
                starting,
                audit_economy_case(
                    vehicle,
                    profile,
                    load,
                    reference,
                    draw,
                    distances[load.distance_band],
                    approach,
                    starting,
                ),
            )
            for label, draw in (("low", 0), ("typical", typical), ("high", 1))
            for approach, starting in ((0, 1), (10, 0.5), (50, 0.1))
        )


def audit_vehicle(model: VehicleModel) -> MarketVehicle:
    """Project catalogue reference facts into an audit-only vehicle context."""
    return MarketVehicle(
        "audit",
        model.id,
        "audit-city",
        "truck",
        model.capacity_tons,
        vehicle_scale_for_segment(model.segment),
        model.transport_capabilities,
        VehicleCostProfile(model.maintenance_eur_per_1000_km / 1000),
        model.energy,
    )


def summarize_economy(
    rows: tuple[EconomyMatrixRow, ...],
) -> EconomyAuditSummary:
    """Summarize reference profitability separately from cashflow."""
    compatible = [row for row in rows if row.result is not None]
    results = [row.result for row in compatible if row.result is not None]
    return EconomyAuditSummary(
        len({row.model_id for row in rows}),
        len(rows),
        len(rows) - len(compatible),
        min(result.reference_margin for result in results),
        sum(result.booked_profit_eur < 0 for result in results),
        sum(
            row.result.booked_profit_eur < 0 and row.load_case == "typical"
            for row in compatible
            if row.result is not None
        ),
    )
