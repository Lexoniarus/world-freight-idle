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
from app.services.routing.evidence import RoutingEvidenceReader
from app.services.routing.preparation import RoutingPreparationService
from tests.support.routing import FakeRouter, FakeRoutingAnchorResolver


def build_test_runtime(synthetic_game, database) -> GameRuntime:
    """Compose a complete local runtime without external providers."""
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    SqliteProviderCache(database)
    readiness_store = SqliteRoutingReadinessStore(database)
    preparation_jobs = SqlitePreparationStore(database)
    world = CachedWorldCatalogue(synthetic_game.world)
    market = MarketComponents(
        MarketCandidateService(
            world, synthetic_game.market.candidates.catalogue
        ),
        synthetic_game.market.factory,
        synthetic_game.market.vehicle_coverage,
    )
    anchors = FakeRoutingAnchorResolver()
    router = FakeRouter()
    routing_evidence = RoutingEvidenceReader(
        readiness_store,
        SqliteRoutingAnchorRepository(database),
        world,
        "test-provider",
        synthetic_game.now,
        anchors.max_snap_distance_m,
    )
    routing_preparation = RoutingPreparationService(
        routing_evidence,
        readiness_store,
        anchors,
        router,
        world,
        synthetic_game.now,
    )
    return GameRuntime(
        database=database,
        world=world,
        router=router,
        anchors=anchors,
        market=market,
        catalogue=synthetic_game.catalogue,
        market_scope=MarketScopeResolver(world),
        routing_evidence=routing_evidence,
        routing_preparation=routing_preparation,
        preparation_jobs=preparation_jobs,
        time_scale=synthetic_game.time_scale,
        clock=synthetic_game.now,
    )
