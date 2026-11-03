"""Shared market composition helpers for behavior tests."""

import time
from typing import TypeVar

from app.bootstrap import PlayerServiceContext, build_player_context
from app.domain.contracts import ContractOffer
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.services.market.demand import MarketDemandResolver
from app.services.market.stock.planning import StockPlanningService
from app.services.market.stock.preparation import StockPreparationBatch
from app.services.market.stock.publication import StockPublicationService
from app.services.market.stock.snapshot import StockSnapshotReader
from app.services.market.templates import MarketTemplateService
from tests.support.game_service import (
    FixtureGameContext,
    FixturePlayerGameFacade,
)
from tests.support.runtime import build_test_runtime

T = TypeVar("T")


def require_value(value: T | None) -> T:
    """Assert and return a value required by a behavior test."""
    assert value is not None
    return value


def seed_test_offers(
    service: FixturePlayerGameFacade,
    count: int = 30,
    *,
    bind_routes: bool = True,
    context: PlayerServiceContext | None = None,
) -> None:
    """Store deterministic local offers without invoking runtime refill."""
    lifecycle = (
        context.lifecycle if context is not None else service.market_lifecycle
    )
    repository = (
        context.state_repository
        if context is not None
        else service.state_repository
    )
    routes = (
        context.market.routes
        if context is not None
        else service.player_market.routes
    )
    market = lifecycle.generation
    owned = repository.list_vehicles()
    fleet = market.candidates.resolve_fleet(owned)
    candidates = market.candidates.build(lifecycle.scope.resolve(owned), fleet)
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
    repository.replace_offers(offers)
    if bind_routes:
        routes.bind(offers)


def make_stock_batch(game: FixturePlayerGameFacade, preparation):
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
    prepared = build_player_context(
        build_test_runtime(context, database),
        "test-owner",
    )
    fixture_service = FixturePlayerGameFacade(
        prepared.unit_of_work,
        prepared.game.now,
        prepared.game.time_scale,
        prepared.lifecycle,
        prepared.initialization,
        prepared.settlement,
        prepared.dispatch,
        prepared.market,
    )
    return (
        FixtureGameContext(
            fixture_service,
            context.world,
            context.catalogue,
            context.market_generation,
            context.market_scope,
        ),
        prepared.market,
    )
