"""Authorize duplicate cleanup only where the catalogue offers diversity."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.domain.market_stock import (
    MarketStockMaintenancePort,
    StockScope,
)
from app.services.market_candidates import MarketCandidateService
from app.services.market_demand import MarketDemandResolver
from app.services.vehicle_coverage import trade_key


@dataclass(slots=True)
class MarketStockMaintenanceService:
    """Separate catalogue decisions from maintenance persistence."""

    candidates: MarketCandidateService
    demand: MarketDemandResolver
    repository: MarketStockMaintenancePort
    clock: Callable[[], float]

    def inspect(self) -> dict[str, int]:
        """Report the safely repairable subset without database writes."""
        return self.repository.inspect(self._repairable_scopes()).report()

    def apply(self, archive: Path) -> dict[str, int | str]:
        """Apply the current deterministic plan with a private archive."""
        plan = self.repository.inspect(self._repairable_scopes())
        return self.repository.apply(plan, archive, self.clock())

    def _repairable_scopes(self) -> frozenset[StockScope]:
        """Require at least two structural trades before removing repeats."""
        duplicates = set(self.repository.duplicate_scopes())
        if not duplicates:
            return frozenset()
        demands = tuple(
            demand
            for demand in self.demand.catalogue(self.clock())
            if any(
                scope[:2] == (demand.vehicle.city_uid, demand.vehicle.model_id)
                for scope in duplicates
            )
        )
        by_city: dict[str, list] = defaultdict(list)
        for demand in demands:
            by_city[demand.vehicle.city_uid].append(demand.vehicle)
        trades: dict[StockScope, set] = defaultdict(set)
        for city_uid, vehicles in by_city.items():
            for candidate in self.candidates.build(
                (city_uid,), tuple(vehicles)
            ):
                for compatible in candidate.vehicles:
                    scope = (
                        city_uid,
                        compatible.vehicle.model_id,
                        candidate.distance_profile.distance_band,
                    )
                    if scope in duplicates:
                        trades[scope].add(trade_key(candidate))
        return frozenset(
            scope for scope, choices in trades.items() if len(choices) > 1
        )
