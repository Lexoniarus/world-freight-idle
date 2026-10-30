"""Production-shaped local runtime composition for tests."""

from app.bootstrap import GameRuntime
from app.repositories.market_preparation import SqlitePreparationStore
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_readiness import SqliteRoutingReadinessStore
from app.services.routing_readiness import RoutingReadinessService
from tests.support.routing import FakeRouter, FakeRoutingAnchorResolver


def build_test_runtime(game, database) -> GameRuntime:
    """Compose a complete local runtime without external providers."""
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    SqliteProviderCache(database)
    readiness_store = SqliteRoutingReadinessStore(database)
    preparation_jobs = SqlitePreparationStore(database)
    readiness = RoutingReadinessService(
        readiness_store,
        FakeRoutingAnchorResolver(),
        SqliteRoutingAnchorRepository(database),
        FakeRouter(),
        game.world,
        "test-provider",
        game.now,
    )
    return GameRuntime(
        database=database,
        world=game.world,
        router=readiness.router,
        anchors=readiness.anchors,
        market=game.market,
        catalogue=game.catalogue,
        market_scope=game.market_scope,
        readiness=readiness,
        preparation_jobs=preparation_jobs,
        time_scale=game.time_scale,
        clock=game.now,
    )
