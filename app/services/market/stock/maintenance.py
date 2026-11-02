"""Plan a narrow offline correction for historically repetitive stock."""

import logging
from dataclasses import dataclass
from pathlib import Path

from app.domain.market_stock import StockPolicy
from app.domain.market_stock_repair import (
    MarketStockRemoval,
    MarketStockRepairContext,
    MarketStockRepairPlan,
    MarketStockRepairReport,
    MarketStockRepairStore,
)
from app.domain.results import AvailableContract
from app.services.market.selection import MarketSelectionService

LOGGER = logging.getLogger(__name__)


def structural_diversity(
    offers: tuple[AvailableContract, ...],
) -> tuple[int, int, int]:
    """Count route, cargo and destination-city variety in visible stock."""
    return (
        len(
            {
                (
                    item.offer.origin.facility_uid,
                    item.offer.destination.facility_uid,
                )
                for item in offers
            }
        ),
        len({item.offer.cargo.nhm_row_id for item in offers}),
        len({item.offer.destination.city.city_uid for item in offers}),
    )


@dataclass(frozen=True, slots=True)
class MarketStockRepairPlanner:
    """Choose minimal removals for prepared, improving alternatives."""

    policy: StockPolicy
    selection: MarketSelectionService

    def plan(
        self,
        contexts: tuple[MarketStockRepairContext, ...],
    ) -> MarketStockRepairPlan:
        """Plan deterministic removals without mutating persistence."""
        removals: list[MarketStockRemoval] = []
        affected = 0
        for context in contexts:
            if len(context.offers) < self.policy.reserve_per_band:
                continue
            current = tuple(
                AvailableContract(item.offer, (context.user_id,))
                for item in context.offers
            )
            alternatives = tuple(
                AvailableContract(template.offer, (context.user_id,))
                for template in context.alternatives
            )
            visible = self.selection.select_diverse_pool(current)
            desired = self.selection.select_diverse_pool(
                (*current, *alternatives)
            )
            if structural_diversity(desired) <= structural_diversity(visible):
                continue
            current_ids = {item.offer.id for item in current}
            alternative_count = sum(
                item.offer.id not in current_ids for item in desired
            )
            visible_ids = {item.offer.id for item in visible}
            removable = tuple(
                item
                for item in reversed(context.offers)
                if item.removable and item.contract_id not in visible_ids
            )[:alternative_count]
            if not removable:
                continue
            affected += 1
            removals.extend(
                MarketStockRemoval(
                    item.user_id,
                    item.contract_id,
                    item.template_id,
                )
                for item in removable
            )
        return MarketStockRepairPlan(
            len(contexts),
            affected,
            tuple(removals),
        )


@dataclass(frozen=True, slots=True)
class MarketStockRepairService:
    """Expose aggregate inspection over an injected offline store."""

    store: MarketStockRepairStore
    planner: MarketStockRepairPlanner

    def inspect(self) -> MarketStockRepairReport:
        """Inspect an immutable source and omit private identities."""
        plan = self.planner.plan(self.store.contexts())
        report = MarketStockRepairReport(
            plan.checked_contexts,
            plan.affected_contexts,
            len(plan.removals),
            len({item.user_id for item in plan.removals}),
        )
        LOGGER.info(
            "Historical market diversity inspected",
            extra={
                "event": "market.stock_repair_inspected",
                "data": {
                    "checked_contexts": report.checked_contexts,
                    "affected_contexts": report.affected_contexts,
                    "offers_to_remove": report.offers_to_remove,
                    "players_to_requeue": report.players_to_requeue,
                },
            },
        )
        return report

    def repair_to(
        self,
        target: Path,
        archive: Path,
        now: float,
    ) -> MarketStockRepairReport:
        """Create a verified repaired copy from the immutable source."""
        plan = self.planner.plan(self.store.contexts())
        self.store.repair_to(plan, target, archive, now)
        report = MarketStockRepairReport(
            plan.checked_contexts,
            plan.affected_contexts,
            len(plan.removals),
            len({item.user_id for item in plan.removals}),
        )
        LOGGER.info(
            "Historical market diversity repaired in a separate copy",
            extra={
                "event": "market.stock_repaired",
                "data": {
                    "affected_contexts": report.affected_contexts,
                    "removed_offers": report.offers_to_remove,
                    "requeued_players": report.players_to_requeue,
                },
            },
        )
        return report
