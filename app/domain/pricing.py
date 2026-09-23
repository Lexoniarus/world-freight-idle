"""Pure economics from the offer and purchased vehicle snapshots."""

from dataclasses import dataclass

from app.domain.validation import require_finite


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """Commercial calculation for one routed contract."""

    payout_eur: int
    operating_cost_eur: int
    profit_eur: int


def calculate_price(
    tons: float,
    distance_km: float,
    operating_cost_eur_per_km: float,
    rate_eur_per_km_ton: float,
) -> PriceQuote:
    """Calculate whole game euros without consulting mutable catalogues."""
    require_finite(tons, "Tonnage", 0.01)
    require_finite(distance_km, "Distance", 0.000001)
    require_finite(operating_cost_eur_per_km, "Kilometer cost")
    require_finite(rate_eur_per_km_ton, "Freight rate")
    payout = round(220 + distance_km * tons * rate_eur_per_km_ton)
    operating_cost = round(80 + distance_km * operating_cost_eur_per_km)
    return PriceQuote(payout, operating_cost, payout - operating_cost)
