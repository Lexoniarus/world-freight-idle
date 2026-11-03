"""Bound visible supply without generating offers or checking providers."""

from dataclasses import dataclass

from app.domain.market_stock import StockPolicy
from app.domain.results import AvailableContract
from app.services.market.diversity import MarketDiversity


@dataclass(frozen=True, slots=True)
class MarketSelectionService:
    """Preserve publication order while limiting each vehicle's bands."""

    policy: StockPolicy

    def select(
        self,
        offers: tuple[AvailableContract, ...],
        vehicle_id: str | None,
    ) -> tuple[AvailableContract, ...]:
        """Select diverse ready slots, including the union for map reads."""
        pools: dict[tuple[str, str], list[AvailableContract]] = {}
        for item in offers:
            context = item.offer.market_context
            if context is None:
                continue
            for uid in item.eligible_vehicle_ids:
                if vehicle_id is None or uid == vehicle_id:
                    pools.setdefault((uid, context.distance_band), []).append(
                        item
                    )
        selected: dict[str, list[str]] = {}
        for (uid, _), pool in pools.items():
            for item in self.select_diverse_pool(tuple(pool)):
                selected.setdefault(item.offer.id, []).append(uid)
        return tuple(
            AvailableContract(
                item.offer,
                tuple(selected[item.offer.id]),
                item.route_reference,
            )
            for item in offers
            if item.offer.id in selected
        )

    def select_diverse_pool(
        self,
        offers: tuple[AvailableContract, ...],
    ) -> tuple[AvailableContract, ...]:
        """Choose a stable diverse slice from one vehicle-distance pool."""
        remaining = list(offers)
        result: list[AvailableContract] = []
        diversity = MarketDiversity()
        while remaining and len(result) < self.policy.visible_per_band:
            index = min(
                range(len(remaining)),
                key=lambda candidate: (
                    diversity.rank_offer(remaining[candidate].offer),
                    candidate,
                ),
            )
            selected = remaining.pop(index)
            result.append(selected)
            diversity.record_offer(selected.offer)
        return tuple(result)
