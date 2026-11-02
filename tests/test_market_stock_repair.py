"""Offline detection of replaceable historical market repetition."""

from dataclasses import asdict, replace
from hashlib import sha256

from app.domain.contracts import ContractOffer
from app.domain.market_stock import PreparedTemplate, StockPolicy
from app.domain.market_stock_repair import (
    MarketStockRepairContext,
    RepairableMarketOffer,
)
from app.repositories.market_stock_repair import SqliteMarketStockRepairStore
from app.services.market.selection import MarketSelectionService
from app.services.market.stock.maintenance import (
    MarketStockRepairPlanner,
    MarketStockRepairService,
)


class MemoryMarketStockRepairStore:
    """Expose explicit contexts behind the production maintenance port."""

    def __init__(self, contexts):
        self._contexts = contexts

    def contexts(self):
        return self._contexts


def _repair_context(diverse_stock_game):
    """Build one full repetitive band with two prepared alternatives."""
    game, _, batch = diverse_stock_game
    snapshot = batch.snapshots.read()
    candidates = []
    signatures = set()
    band = snapshot.candidates[0].distance_profile.distance_band
    for candidate in snapshot.candidates:
        if candidate.distance_profile.distance_band != band:
            continue
        signature = (
            candidate.trade.origin.facility_uid,
            candidate.trade.destination.facility_uid,
            candidate.trade.cargo.nhm_row_id,
        )
        if signature not in signatures:
            signatures.add(signature)
            candidates.append(candidate)
        if len(candidates) == 3:
            break
    assert len(candidates) == 3
    factory = game.market_lifecycle.market.factory
    base = ContractOffer.from_snapshot(factory.build(candidates[0], 1, "base"))
    offers = tuple(
        RepairableMarketOffer(
            "test-owner",
            f"contract-{index}",
            f"template-{index}",
            replace(base, id=f"contract-{index}"),
            True,
        )
        for index in range(10)
    )
    alternatives = tuple(
        PreparedTemplate(
            f"alternative-{index}",
            snapshot.demands[0].vehicle.model_id,
            snapshot.demands[0].vehicle.city_uid,
            replace(
                ContractOffer.from_snapshot(
                    factory.build(candidate, 1, f"alternative:{index}")
                ),
                id=f"alternative-offer-{index}",
            ),
        )
        for index, candidate in enumerate(candidates[1:], 1)
    )
    return MarketStockRepairContext(
        "test-owner",
        snapshot.demands[0].vehicle.city_uid,
        snapshot.demands[0].vehicle.model_id,
        band,
        offers,
        alternatives,
    )


def _repair_service(contexts):
    """Compose maintenance with the production diversity selector."""
    policy = StockPolicy()
    return MarketStockRepairService(
        MemoryMarketStockRepairStore(contexts),
        MarketStockRepairPlanner(
            policy,
            MarketSelectionService(policy),
        ),
    )


def test_market_stock_repair_plans_only_prepared_improvements(
    diverse_stock_game,
):
    """Plan minimal aggregate cleanup and preserve valid repetition."""
    context = _repair_context(diverse_stock_game)

    report = _repair_service((context,)).inspect()

    assert asdict(report) == {
        "checked_contexts": 1,
        "affected_contexts": 1,
        "offers_to_remove": 2,
        "players_to_requeue": 1,
    }
    assert (
        _repair_service((replace(context, alternatives=()),))
        .inspect()
        .offers_to_remove
        == 0
    )
    protected = replace(
        context,
        offers=tuple(
            replace(item, removable=False) for item in context.offers
        ),
    )
    assert _repair_service((protected,)).inspect().offers_to_remove == 0


def test_market_stock_repair_store_reads_source_without_mutation(
    diverse_stock_game,
    database,
):
    """Decode persisted contexts through a query-only source connection."""
    _, preparation, _ = diverse_stock_game
    context = _repair_context(diverse_stock_game)
    with database.transaction():
        for item in context.offers:
            preparation.stock.templates.add(
                PreparedTemplate(
                    item.template_id,
                    context.model_id,
                    context.city_uid,
                    item.offer,
                )
            )
            preparation.stock.stock.issue(item.template_id, item.offer)
        for template in context.alternatives:
            preparation.stock.templates.add(template)
    before = sha256(database.path.read_bytes()).hexdigest()

    stored = SqliteMarketStockRepairStore(database.path).contexts()

    assert sha256(database.path.read_bytes()).hexdigest() == before
    selected = next(
        item for item in stored if item.distance_band == context.distance_band
    )
    assert len(selected.offers) == 10
    assert len(selected.alternatives) == 2
    assert all(item.removable for item in selected.offers)
