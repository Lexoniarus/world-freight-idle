"""Shared market composition helpers for behavior tests."""

import time
from typing import TypeVar

from app.bootstrap import build_player_service
from app.domain.contracts import ContractOffer
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.services.gameplay.player_game import PlayerGameFacade
from app.services.market.demand import MarketDemandResolver
from app.services.market.stock.planning import StockPlanningService
from app.services.market.stock.preparation import StockPreparationBatch
from app.services.market.stock.publication import StockPublicationService
from app.services.market.stock.snapshot import StockSnapshotReader
from app.services.market.templates import MarketTemplateService
from tests.support.game_service import FixtureGameContext
from tests.support.runtime import build_test_runtime

T = TypeVar("T")


def require_value(value: T | None) -> T:
    """Assert and return a value required by a behavior test."""
    assert value is not None
    return value


def seed_test_offers(
    service: PlayerGameFacade,
    count: int = 30,
    *,
    bind_routes: bool = True,
) -> None:
    """Store deterministic local offers without invoking runtime refill."""
    market = service.market_lifecycle.generation
    owned = service.state_repository.list_vehicles()
    fleet = market.candidates.resolve_fleet(owned)
    candidates = market.candidates.build(
        service.market_lifecycle.scope.resolve(owned), fleet
    )
    local = tuple(
        candidate
        for candidate in candidates
        if candidate.trade.origin.facility_uid == owned[0].facility_uid
    )
    selected = (*local[:10], *(c for c in candidates if c not in local))
    offers = tuple(
        ContractOffer.from_snapshot(
            market.contract_factory.build(
                candidate,
                time.time(),
                f"fixture:{index}",
            )
        )
        for index, candidate in enumerate(selected[:count])
    )
    service.state_repository.replace_offers(offers)
    if bind_routes:
        service.player_market.routes.bind(offers)


def make_stock_batch(game: PlayerGameFacade, preparation):
    """Compose the production stock batch for worker behavior tests."""
    market = game.market_lifecycle.generation
    database = preparation.routes.transactions
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    demand = MarketDemandResolver(market.candidates)
    return StockPreparationBatch(
        StockPublicationService(
            game.unit_of_work,
            market,
            preparation.demand,
            preparation.routes,
            preparation.stores,
            lambda: True,
        ),
        StockSnapshotReader(
            game.unit_of_work,
            market,
            preparation.demand,
            preparation.routes,
            preparation.stores,
            demand,
        ),
        StockPlanningService(preparation.stores.policy),
        MarketTemplateService(
            market.contract_factory,
            preparation.stores.policy,
            preparation.demand.clock,
        ),
        preparation.route_preparation,
    )


def build_prepared_game(context: FixtureGameContext, database):
    """Recompose one game with real local preparation collaborators."""
    prepared = build_player_service(
        build_test_runtime(context, database),
        "test-owner",
    )
    return (
        FixtureGameContext(
            prepared,
            context.world,
            context.catalogue,
            context.market_generation,
            context.market_scope,
        ),
        prepared.player_market,
    )
