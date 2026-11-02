"""Production-shaped local runtime composition for tests."""

from app.bootstrap import GameRuntime
from app.repositories.cached_world_catalogue import CachedWorldCatalogue
from app.repositories.market_preparation import SqlitePreparationStore
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_readiness import SqliteRoutingReadinessStore
from app.services.market.candidates import MarketCandidateService
from app.services.market.generation_services import MarketGenerationServices
from app.services.market.scope import MarketScopeResolver
from app.services.routing.evidence import RoutingEvidenceReader
from app.services.routing.preparation import RoutingPreparationService
from tests.support.game_service import FixtureGameContext
from tests.support.routing import FakeRouter, FakeRoutingAnchorResolver


def build_test_runtime(
    context: FixtureGameContext,
    database,
) -> GameRuntime:
    """Compose a complete local runtime without external providers."""
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    SqliteProviderCache(database)
    readiness_store = SqliteRoutingReadinessStore(database)
    preparation_jobs = SqlitePreparationStore(database)
    world = CachedWorldCatalogue(context.world)
    market_generation = MarketGenerationServices(
        MarketCandidateService(
            world,
            context.market_generation.candidates.catalogue,
        ),
        context.market_generation.contract_factory,
        context.market_generation.coverage,
    )
    anchors = FakeRoutingAnchorResolver()
    router = FakeRouter()
    routing_evidence = RoutingEvidenceReader(
        readiness_store,
        SqliteRoutingAnchorRepository(database),
        world,
        "test-provider",
        context.service.now,
        anchors.max_snap_distance_m,
    )
    routing_preparation = RoutingPreparationService(
        routing_evidence,
        readiness_store,
        anchors,
        router,
        world,
        context.service.now,
    )
    return GameRuntime(
        database=database,
        world=world,
        market_generation=market_generation,
        catalogue=context.catalogue,
        market_scope=MarketScopeResolver(world),
        routing_evidence=routing_evidence,
        routing_preparation=routing_preparation,
        preparation_jobs=preparation_jobs,
        time_scale=context.service.time_scale,
        clock=context.service.now,
    )
