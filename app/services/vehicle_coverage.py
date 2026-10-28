"""Plan shared offers that satisfy each idle vehicle's usable market."""

from dataclasses import dataclass, replace

from app.domain.contracts import ContractOffer
from app.domain.market import (
    CompatibleVehicle,
    MarketCandidate,
    MarketVehicle,
    VehicleCoverageDiagnostic,
)
from app.domain.market_compatibility import can_carry_offer
from app.domain.market_profiles import DISTANCE_BANDS


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
    """Report prepared offer coverage for one market vehicle."""

    visible_per_band: int = 3

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
                if b in bands and count < self.visible_per_band
            ),
            tuple(sorted(origins - covered)),
        )


def trade_key(candidate: MarketCandidate) -> tuple[str, str, int]:
    """Index compatible contexts by the stable trade identity."""
    return (
        candidate.trade.origin.facility_uid,
        candidate.trade.destination.facility_uid,
        candidate.trade.cargo.nhm_row_id,
    )
