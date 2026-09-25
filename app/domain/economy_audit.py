"""Deterministic economy scenarios using the production domain rules."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.economics import ENERGY_PRICES, journey_costs
from app.domain.journeys import plan_journey
from app.domain.market import MarketVehicle
from app.domain.market_calculations import biased_load_factor, shipment_tons
from app.domain.market_profiles import DistanceLoadProfile, NhmMarketProfile
from app.domain.pricing import calculate_price
from app.domain.tariffs import freight_tariff
from app.simulation import STANDARD_RATE


@dataclass(frozen=True, slots=True)
class EconomyAuditResult:
    """Separate normalized profitability from up-front purchase cashflow."""

    load_factor: float
    tons: float
    maintenance_cost_eur: int
    energy_consumption: float
    energy_purchase_eur: int
    minimum_freight_eur_per_km: float
    payout_eur: int
    booked_cost_eur: int
    booked_profit_eur: int
    reference_margin: float


def audit_economy_case(
    vehicle: MarketVehicle,
    profile: NhmMarketProfile,
    load: DistanceLoadProfile,
    reference_factor: float,
    draw: float,
    distance_km: float,
    approach_km: float = 0,
    starting_fraction: float = 1,
) -> EconomyAuditResult:
    """Evaluate one reproducible load with stored tariff and journey rules."""
    factor = biased_load_factor(
        load.load_factor_min, load.load_factor_max, draw
    )
    tons = shipment_tons(vehicle.capacity_tons, factor)
    tariff = freight_tariff(
        vehicle.cost_profile,
        vehicle.energy,
        profile.freight_rate_factor_game,
        reference_factor,
    )
    journey = plan_journey(
        distance_km + approach_km,
        (distance_km + approach_km) * 60,
        100,
        vehicle.energy,
        vehicle.energy.capacity * starting_fraction,
        1,
    )
    costs = journey_costs(journey, vehicle.cost_profile)
    price = calculate_price(
        tons,
        distance_km,
        costs,
        STANDARD_RATE * profile.freight_rate_factor_game,
        minimum_eur_per_km=tariff.minimum_eur_per_km,
    )
    reference_cost = Decimal(80) + Decimal(str(distance_km)) * (
        Decimal(str(vehicle.cost_profile.maintenance_eur_per_km))
        + Decimal(str(vehicle.energy.consumption_per_100km))
        / 100
        * ENERGY_PRICES[vehicle.energy.kind]
    )
    margin = (Decimal(price.payout_eur) - reference_cost) / price.payout_eur
    return EconomyAuditResult(
        factor,
        tons,
        costs.maintenance_cost_eur,
        vehicle.energy.consumption_for(journey.distance_km),
        costs.energy_cost_eur,
        tariff.minimum_eur_per_km,
        price.payout_eur,
        costs.total_cost_eur,
        price.profit_eur,
        float(margin),
    )
