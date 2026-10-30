"""Shared market composition helpers for behavior tests."""

import time
from typing import TypeVar

from app.domain.contracts import ContractOffer
from app.repositories.cached_world_catalogue import CachedWorldCatalogue
from app.repositories.market_preparation import SqlitePreparationStore
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_readiness import (
    SqliteOfferRouteStore,
    SqliteRoutingReadinessStore,
)
from app.services.game import GameService
from app.services.market_demand import MarketDemandResolver
from app.services.market_route_preparation import (
    MarketRoutePreparationService,
)
from app.services.market_selection import MarketSelectionService
from app.services.market_templates import MarketTemplateService
from app.services.player_market_demand import PlayerMarketDemandService
from app.services.player_market_routes import PlayerMarketRouteService
from app.services.player_market_services import PlayerMarketServices
from app.services.player_market_stock import PlayerMarketStockContext
from app.services.routing_readiness import RoutingReadinessService
from app.services.stock_planning import StockPlanningService
from app.services.stock_preparation import StockPreparationBatch
from app.services.stock_publication import StockPublicationService
from app.services.stock_snapshot import StockSnapshotReader
from tests.support.routing import FakeRouter, FakeRoutingAnchorResolver

T = TypeVar("T")


def require_value(value: T | None) -> T:
    """Assert and return a value required by a behavior test."""
    assert value is not None
    return value


def seed_test_offers(service: GameService, count: int = 30) -> None:
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
    service.market_services.routes.bind(offers)


def make_stock_batch(game, preparation):
    """Compose the production stock batch for worker behavior tests."""
    database = preparation.routes.transactions
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    game.market_lifecycle.selection = MarketSelectionService(
        preparation.stock.policy
    )
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


def bind_preparation(game, database):
    """Bind production preparation collaborators to a legacy game fixture."""
    game.world = CachedWorldCatalogue(game.world)
    game.market.candidates.world = game.world
    SqliteProviderCache(database)
    store = SqliteRoutingReadinessStore(database)
    jobs = SqlitePreparationStore(database)
    anchor_store = SqliteRoutingAnchorRepository(database)
    readiness = RoutingReadinessService(
        store,
        FakeRoutingAnchorResolver(),
        anchor_store,
        FakeRouter(),
        CachedWorldCatalogue(game.world),
        "test-provider",
        game.now,
    )
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    preparation = PlayerMarketServices(
        PlayerMarketDemandService("test-owner", jobs, game.now, database),
        PlayerMarketRouteService(
            readiness,
            SqliteOfferRouteStore(database, "test-owner"),
            database,
        ),
        MarketRoutePreparationService(readiness, game.now),
        PlayerMarketStockContext(
            SqlitePlayerMarketStockStore(database, "test-owner"),
            SqliteMarketTemplateStore(database),
        ),
    )
    game.market_lifecycle.demand = preparation.demand
    game.market_lifecycle.routes = preparation.routes
    game.market_lifecycle.stock = preparation.stock
    game.market_lifecycle.selection = MarketSelectionService(
        preparation.stock.policy
    )
    game.initialization.market_demand = preparation.demand
    game.settlement.market_demand = preparation.demand
    game.transport_dispatch.planning.routes = preparation.routes
    game.transport_dispatch.stock = preparation.stock
    game.transport_dispatch.market_demand = preparation.demand
    game.market_services = preparation
    return preparation
