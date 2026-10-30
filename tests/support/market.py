"""Shared market composition helpers for behavior tests."""

import time
from typing import TypeVar

from app.bootstrap import build_player_service
from app.domain.contracts import ContractOffer
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.services.game import GameService
from app.services.market_demand import MarketDemandResolver
from app.services.market_templates import MarketTemplateService
from app.services.stock_planning import StockPlanningService
from app.services.stock_preparation import StockPreparationBatch
from app.services.stock_publication import StockPublicationService
from app.services.stock_snapshot import StockSnapshotReader
from tests.support.runtime import build_test_runtime

T = TypeVar("T")


def require_value(value: T | None) -> T:
    """Assert and return a value required by a behavior test."""
    assert value is not None
    return value


def seed_test_offers(
    service: GameService,
    count: int = 30,
    *,
    bind_routes: bool = True,
) -> None:
    """Store deterministic local offers without invoking runtime refill."""
    market = service.market
    owned = service.state_repository.list_vehicles()
    fleet = market.candidates.resolve_fleet(owned)
    candidates = market.candidates.build(
        service.market_scope.resolve(owned), fleet
    )
    local = tuple(
        candidate
        for candidate in candidates
        if candidate.trade.origin.facility_uid == owned[0].facility_uid
    )
    selected = (*local[:10], *(c for c in candidates if c not in local))
    offers = tuple(
        ContractOffer.from_snapshot(
            market.factory.build(
                candidate,
                time.time(),
                f"fixture:{index}",
            )
        )
        for index, candidate in enumerate(selected[:count])
    )
    service.state_repository.replace_offers(offers)
    if bind_routes:
        service.market_services.routes.bind(offers)


def make_stock_batch(game, preparation):
    """Compose the production stock batch for worker behavior tests."""
    database = preparation.routes.transactions
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    demand = MarketDemandResolver(game.market.candidates)
    return StockPreparationBatch(
        StockPublicationService(
            game.unit_of_work,
            game.market,
            preparation.demand,
            preparation.routes,
            preparation.stock,
            lambda: True,
        ),
        StockSnapshotReader(
            game.unit_of_work,
            game.market,
            preparation.demand,
            preparation.routes,
            preparation.stock,
            demand,
        ),
        StockPlanningService(preparation.stock.policy),
        MarketTemplateService(
            game.market.factory,
            preparation.stock.policy,
            preparation.demand.clock,
        ),
        preparation.route_preparation,
    )


def build_prepared_game(game, database):
    """Recompose one game with real local preparation collaborators."""
    prepared = build_player_service(
        build_test_runtime(game, database),
        "test-owner",
    )
    return prepared, prepared.market_services
