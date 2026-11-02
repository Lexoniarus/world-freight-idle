"""Bound visible supply without generating offers or checking providers."""

from collections import Counter
from dataclasses import dataclass

from app.domain.market_stock import StockPolicy
from app.domain.results import AvailableContract


@dataclass(frozen=True, slots=True)
class MarketSelectionService:
    """Preserve publication order while limiting each vehicle's bands."""

    policy: StockPolicy

    def select(
        self,
        offers: tuple[AvailableContract, ...],
        vehicle_id: str | None,
    ) -> tuple[AvailableContract, ...]:
        """Select the first ready slots, including the union for map reads."""
        counts: Counter[tuple[str, str]] = Counter()
        result = []
        for item in offers:
            context = item.offer.market_context
            if context is None:
                continue
            eligible = tuple(
                uid
                for uid in item.eligible_vehicle_ids
                if (vehicle_id is None or uid == vehicle_id)
                and counts[uid, context.distance_band]
                < self.policy.visible_per_band
            )
            if eligible:
                result.append(
                    AvailableContract(
                        item.offer,
                        eligible,
                        item.route_reference,
                    )
                )
                for uid in eligible:
                    counts[uid, context.distance_band] += 1
        return tuple(result)
