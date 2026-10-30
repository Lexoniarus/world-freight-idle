"""Production-shaped local runtime composition for tests."""

from app.bootstrap import GameRuntime
from app.repositories.cached_world_catalogue import CachedWorldCatalogue
from app.repositories.market_preparation import SqlitePreparationStore
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_readiness import SqliteRoutingReadinessStore
from app.services.market_candidates import MarketCandidateService
from app.services.market_components import MarketComponents
from app.services.market_scope import MarketScopeResolver
from app.services.routing_readiness import RoutingReadinessService
from tests.support.routing import FakeRouter, FakeRoutingAnchorResolver


def build_test_runtime(game, database) -> GameRuntime:
    """Compose a complete local runtime without external providers."""
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    SqliteProviderCache(database)
    readiness_store = SqliteRoutingReadinessStore(database)
    preparation_jobs = SqlitePreparationStore(database)
    world = CachedWorldCatalogue(game.world)
    market = MarketComponents(
        MarketCandidateService(world, game.market.candidates.catalogue),
        game.market.factory,
        game.market.vehicle_coverage,
    )
    readiness = RoutingReadinessService(
        readiness_store,
        FakeRoutingAnchorResolver(),
        SqliteRoutingAnchorRepository(database),
        FakeRouter(),
        world,
        "test-provider",
        game.now,
    )
    return GameRuntime(
        database=database,
        world=world,
        router=readiness.router,
        anchors=readiness.anchors,
        market=market,
        catalogue=game.catalogue,
        market_scope=MarketScopeResolver(world),
        readiness=readiness,
        preparation_jobs=preparation_jobs,
        time_scale=game.time_scale,
        clock=game.now,
    )
