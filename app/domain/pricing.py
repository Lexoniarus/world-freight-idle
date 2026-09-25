"""Pure economics from the offer and purchased vehicle snapshots."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.economics import CostBreakdown, whole_euros
from app.domain.validation import require_finite


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """Commercial calculation for one routed contract."""

    payout_eur: int
    operating_cost_eur: int
    profit_eur: int
    cost_breakdown: CostBreakdown | None = None


def calculate_price(
    tons: float,
    distance_km: float,
    costs: CostBreakdown,
    rate_eur_per_km_ton: float,
    *,
    minimum_eur_per_km: float = 0.0,
) -> PriceQuote:
    """Calculate whole game euros without consulting mutable catalogues."""
    require_finite(tons, "Tonnage", 0.01)
    require_finite(distance_km, "Distance", 0.000001)
    require_finite(rate_eur_per_km_ton, "Freight rate")
    require_finite(minimum_eur_per_km, "Minimum freight")
    rate = max(
        Decimal(str(tons)) * Decimal(str(rate_eur_per_km_ton)),
        Decimal(str(minimum_eur_per_km)),
    )
    payout = whole_euros(Decimal(220) + Decimal(str(distance_km)) * rate)
    if not isinstance(costs, CostBreakdown):
        raise ValueError("Pricing requires an explicit cost breakdown.")
    operating_cost = costs.total_cost_eur
    return PriceQuote(payout, operating_cost, payout - operating_cost, costs)
