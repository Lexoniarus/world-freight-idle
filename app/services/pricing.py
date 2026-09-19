"""Simple MVP economics for freight contracts."""

from __future__ import annotations

from app.domain.models import CargoType, PriceQuote


class PricingService:
    """Calculate payout, cost and profit from routed distance and cargo."""

    def __init__(self, cargo_types: tuple[CargoType, ...]) -> None:
        self._rates = {
            cargo.name: cargo.rate_eur_per_km_ton for cargo in cargo_types
        }

    def quote(
        self,
        cargo_name: str,
        tons: float,
        distance_km: float,
        operating_cost_eur_per_km: float = 0.62,
        rate_eur_per_km_ton: float | None = None,
    ) -> PriceQuote:
        """Price one contract from its real routed distance."""
        rate = (
            self._rates.get(cargo_name, 0.18)
            if rate_eur_per_km_ton is None
            else rate_eur_per_km_ton
        )
        payout = round(220 + distance_km * tons * rate)
        operating_cost = round(80 + distance_km * operating_cost_eur_per_km)
        return PriceQuote(
            payout_eur=payout,
            operating_cost_eur=operating_cost,
            profit_eur=payout - operating_cost,
        )
