"""Plan shared offers that satisfy each idle vehicle's usable market."""

from dataclasses import dataclass, replace

from app.domain.contracts import ContractOffer
from app.domain.market import (
    CompatibleVehicle,
    CoveragePlan,
    MarketCandidate,
    MarketVehicle,
    VehicleCoverageDiagnostic,
)
from app.domain.market_compatibility import can_carry_offer
from app.domain.market_profiles import DISTANCE_BANDS
from app.services.market_coverage import (
    MINIMUM_DISTANCE_OFFERS,
    MarketCoverageService,
)


def restrict_candidate(
    candidate: MarketCandidate,
    vehicles: tuple[CompatibleVehicle, ...],
) -> MarketCandidate:
    """Preserve evidence weights while narrowing eligible contexts."""
    weight = candidate.weight * max(v.suitability for v in vehicles)
    weight /= max(v.suitability for v in candidate.vehicles)
    return replace(candidate, vehicles=vehicles, weight=weight)


def vehicle_candidates(
    candidates: tuple[MarketCandidate, ...],
    vehicle: MarketVehicle,
) -> tuple[MarketCandidate, ...]:
    """Select feasible generation contexts whose shipments fit the target."""
    return tuple(
        restrict_candidate(
            c,
            tuple(
                v
                for v in c.vehicles
                if v.vehicle.capacity_tons <= vehicle.capacity_tons
            ),
        )
        for c in candidates
        if any(v.vehicle.vehicle_id == vehicle.vehicle_id for v in c.vehicles)
    )


def vehicle_offers(
    offers: tuple[ContractOffer, ...],
    vehicle: MarketVehicle,
    ready: tuple[MarketCandidate, ...],
) -> tuple[ContractOffer, ...]:
    """Count actual tonnage only with ready delivery and vehicle approach."""
    profiles = {
        (
            c.trade.origin.facility_uid,
            c.trade.destination.facility_uid,
            c.profile.nhm_row_id,
        ): c.profile
        for c in ready
        if any(v.vehicle.vehicle_id == vehicle.vehicle_id for v in c.vehicles)
    }
    return tuple(
        o
        for o in offers
        if (
            profile := profiles.get(
                (
                    o.origin.facility_uid,
                    o.destination.facility_uid,
                    o.cargo.nhm_row_id,
                )
            )
        )
        is not None
        and can_carry_offer(vehicle, o, profile)
    )


@dataclass(slots=True)
class VehicleCoverageService:
    """Extend city coverage with bounded, shareable vehicle coverage."""

    coverage: MarketCoverageService

    def extend(
        self,
        plan: CoveragePlan,
        candidates: tuple[MarketCandidate, ...],
        offers: tuple[ContractOffer, ...],
        fleet: tuple[MarketVehicle, ...],
        ready: tuple[MarketCandidate, ...],
    ) -> CoveragePlan:
        """Plan smaller generation contexts first to share fitting offers."""
        selected = list(plan.selected)
        for vehicle in sorted(
            fleet, key=lambda v: (v.capacity_tons, v.vehicle_id)
        ):
            pool = vehicle_candidates(candidates, vehicle)
            existing = vehicle_offers(offers, vehicle, ready)
            guaranteed = tuple(
                c
                for c in selected
                if any(
                    v.vehicle.vehicle_id == vehicle.vehicle_id
                    for v in candidates_for_trade(c, candidates)
                )
                and max(v.vehicle.capacity_tons for v in c.vehicles)
                <= vehicle.capacity_tons
            )
            additions = self.coverage.plan(
                (vehicle.city_uid,),
                pool,
                existing,
                guaranteed,
            )
            selected.extend(additions.selected)
        return CoveragePlan(tuple(selected), plan.diagnostics)

    def diagnose(
        self,
        vehicle: MarketVehicle,
        structural: tuple[MarketCandidate, ...],
        ready: tuple[MarketCandidate, ...],
        offers: tuple[ContractOffer, ...],
    ) -> VehicleCoverageDiagnostic:
        """Report actual coverage against structurally possible targets."""
        pool = vehicle_candidates(structural, vehicle)
        eligible = vehicle_offers(offers, vehicle, ready)
        bands = {c.distance_profile.distance_band for c in pool}
        counts = tuple(
            sum(
                o.market_context is not None
                and o.market_context.distance_band == band
                for o in eligible
            )
            for band in DISTANCE_BANDS
        )
        origins = {c.trade.origin.facility_uid for c in pool}
        covered = {o.origin.facility_uid for o in eligible}
        return VehicleCoverageDiagnostic(
            vehicle.vehicle_id,
            vehicle.city_uid,
            len(eligible),
            (counts[0], counts[1], counts[2]),
            tuple(
                b
                for b, count in zip(DISTANCE_BANDS, counts)
                if b in bands and count < MINIMUM_DISTANCE_OFFERS
            ),
            tuple(sorted(origins - covered)),
        )


def candidates_for_trade(
    candidate: MarketCandidate,
    pool: tuple[MarketCandidate, ...],
) -> tuple[CompatibleVehicle, ...]:
    """Recover all compatible contexts before generation-capacity narrowing."""
    return tuple(
        v for c in pool if c.trade == candidate.trade for v in c.vehicles
    )
