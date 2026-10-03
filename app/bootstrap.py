"""Dependency assembly for production and test application instances."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import httpx

from app.config import Settings
from app.domain.game_import import GameStateImporter
from app.domain.geography_migration import GeographyMigrationStore
from app.domain.market_stock import StockPolicy
from app.domain.ports import TruckRouter, VehicleCatalogue, WorldCatalogue
from app.domain.read_ports import LeaderboardReader, TrafficReader
from app.domain.routing_anchor_ports import RoutingAnchorResolverPort
from app.domain.world_scopes import WorldScope
from app.providers.geocoding import NominatimGeocoder
from app.providers.request_limiter import ProviderRequestLimiter
from app.providers.routing import ValhallaTruckRouter
from app.providers.routing_anchor import ValhallaTruckAnchorLocator
from app.repositories.accounts import AccountRepository
from app.repositories.analytics import SqliteAnalyticsReader
from app.repositories.cached_vehicle_catalogue import CachedVehicleCatalogue
from app.repositories.cached_world_catalogue import CachedWorldCatalogue
from app.repositories.energy_upgrade import VehicleEnergyUpgradeRepository
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.repositories.leaderboard import SqliteLeaderboardReader
from app.repositories.legacy_game_import import LegacyGameImporter
from app.repositories.market_preparation import SqlitePreparationStore
from app.repositories.market_startup import SqliteMarketStartupStore
from app.repositories.market_stock import (
    SqliteMarketStockStore,
    SqliteMarketTemplateStore,
)
from app.repositories.market_stock_maintenance import (
    MarketStockMaintenanceRepository,
)
from app.repositories.market_stock_upgrade import MarketStockUpgradeRepository
from app.repositories.postgres_catalogues import (
    PostgresVehicleCatalogue,
    PostgresWorldCatalogue,
)
from app.repositories.postgres_database import PostgresGameDatabase
from app.repositories.preferences import SqlitePreferenceStore
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.relational_traffic import SqliteTrafficReader
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_audit import SqliteRoutingAudit
from app.repositories.routing_readiness import (
    SqliteOfferRouteStore,
    SqliteRoutingReadinessStore,
)
from app.repositories.runtime_views import SqliteRuntimeReader
from app.repositories.transport_repair import TransportRepairRepository
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.repositories.world_geography import WorldGeographyRepository
from app.services.analytics import AnalyticsService
from app.services.contract_factory import ContractFactory
from app.services.cost_profiles import VehicleCostResolver
from app.services.dispatch_planning import DispatchPlanningService
from app.services.economy_audit import EconomyAuditService
from app.services.fleet import FleetService
from app.services.game import GameService
from app.services.global_stock_preparation import GlobalStockPreparationBatch
from app.services.map_locations import MapLocationService
from app.services.market import MarketGenerator
from app.services.market_candidates import MarketCandidateService
from app.services.market_coverage import MarketCoverageService
from app.services.market_demand import MarketDemandResolver
from app.services.market_lifecycle import MarketLifecycleService
from app.services.market_preparation import MarketPreparationService
from app.services.market_scope import MarketScopeResolver
from app.services.market_selection import MarketSelectionService
from app.services.market_startup import MarketStartupService
from app.services.market_stock_maintenance import (
    MarketStockMaintenanceService,
)
from app.services.market_templates import MarketTemplateService
from app.services.preferences import PreferenceService
from app.services.preparation_lease import PreparationLease
from app.services.preparation_worker import MarketPreparationWorker
from app.services.profile_maintenance import ProfileMaintenanceService
from app.services.routing_anchors import RoutingAnchorResolver
from app.services.routing_readiness import RoutingReadinessService
from app.services.runtime_views import RuntimeViewService
from app.services.stock_planning import StockPlanningService
from app.services.stock_preparation import StockPreparationBatch
from app.services.stock_publication import StockPublicationService
from app.services.vehicle_coverage import VehicleCoverageService


@dataclass
class GameRuntime:
    """Shared dependencies owned by the application composition root."""

    database: SqliteGameDatabase
    world: WorldCatalogue
    router: TruckRouter
    anchors: RoutingAnchorResolverPort
    market: MarketGenerator
    catalogue: VehicleCatalogue
    market_scope: MarketScopeResolver
    time_scale: float
    clock: Callable[[], float] = time.time
    readiness: RoutingReadinessService | None = None
    preparation_jobs: SqlitePreparationStore | None = None
    template_store: SqliteMarketTemplateStore | None = None


def build_analytics_service(
    runtime: GameRuntime, user_id: str
) -> AnalyticsService:
    """Bind private analytics to an authenticated account."""
    return AnalyticsService(SqliteAnalyticsReader(runtime.database, user_id))


def build_routing_anchor_resolver(
    database: SqliteGameDatabase,
    settings: Settings,
    provider_client: httpx.AsyncClient,
    clock: Callable[[], float],
    limiter: ProviderRequestLimiter | None = None,
    evidence: SqliteRoutingReadinessStore | None = None,
) -> RoutingAnchorResolver:
    """Wire global truck anchors outside immutable world references."""
    cache = SqliteProviderCache(database)
    return RoutingAnchorResolver(
        store=SqliteRoutingAnchorRepository(database),
        locator=ValhallaTruckAnchorLocator(
            provider_client,
            settings.valhalla_url,
            settings.valhalla_client_id,
            limiter,
            partial(evidence.observe_provider_revision, settings.valhalla_url)
            if evidence
            else None,
        ),
        geocoder=NominatimGeocoder(
            cache,
            provider_client,
            settings.nominatim_url,
            settings.http_user_agent,
        ),
        max_snap_distance_m=settings.routing_anchor_max_snap_m,
        clock=clock,
        evidence=evidence,
        provider_revision=partial(
            evidence.provider_revision, settings.valhalla_url
        )
        if evidence
        else None,
    )


def build_game_database(settings: Settings) -> SqliteGameDatabase:
    """Select PostgreSQL for production and SQLite for local fixtures."""
    if settings.database_url:
        return PostgresGameDatabase(
            settings.database_url,
            settings.game_database_schema,
            settings.database_pool_size,
        )
    return SqliteGameDatabase(settings.db_path)


def build_game_runtime(
    settings: Settings,
    routing_client: httpx.AsyncClient,
    rng_seed: int | None = None,
) -> GameRuntime:
    """Initialize only relational storage and shared application resources."""
    database = build_game_database(settings)
    database.initialize()
    cache = SqliteProviderCache(database)
    evidence = SqliteRoutingReadinessStore(database)
    jobs = SqlitePreparationStore(database)
    SqliteMarketStockStore.initialize(database)
    templates = SqliteMarketTemplateStore(database)
    limiter = ProviderRequestLimiter(
        settings.valhalla_concurrency, settings.valhalla_minimum_interval
    )
    router = ValhallaTruckRouter(
        cache=cache,
        client=routing_client,
        base_url=settings.valhalla_url,
        client_id=settings.valhalla_client_id,
        limiter=limiter,
        cache_enabled=False,
        revision_observer=partial(
            evidence.observe_provider_revision, settings.valhalla_url
        ),
    )
    world = build_world_catalogue(settings)
    catalogue = CachedVehicleCatalogue(build_vehicle_catalogue(settings))
    clock = time.time
    anchors = build_routing_anchor_resolver(
        database, settings, routing_client, clock, limiter, evidence
    )
    readiness = RoutingReadinessService(
        evidence,
        anchors,
        SqliteRoutingAnchorRepository(database),
        router,
        world,
        settings.valhalla_url,
        clock,
        provider_revision=partial(
            evidence.provider_revision, settings.valhalla_url
        ),
    )
    return GameRuntime(
        readiness=readiness,
        preparation_jobs=jobs,
        template_store=templates,
        database=database,
        world=world,
        router=router,
        anchors=anchors,
        market=build_market_generator(
            world, random.Random(rng_seed), catalogue
        ),
        catalogue=catalogue,
        market_scope=MarketScopeResolver(world),
        time_scale=settings.game_time_scale,
        clock=clock,
    )


def build_player_service(runtime: GameRuntime, user_id: str) -> GameService:
    """Bind one authenticated owner to the shared relational transaction."""
    preparation = build_market_preparation(runtime, user_id)
    game = GameService(
        preparation=preparation,
        market_selection=(
            MarketSelectionService(preparation.policy) if preparation else None
        ),
        unit_of_work=SqliteGameUnitOfWork(runtime.database, user_id),
        world=runtime.world,
        router=runtime.router,
        dispatch_planning=DispatchPlanningService(
            runtime.router,
            VehicleCostResolver(runtime.catalogue),
            runtime.anchors,
            runtime.world,
            preparation,
        ),
        market=runtime.market,
        catalogue=runtime.catalogue,
        market_scope=runtime.market_scope,
        time_scale=runtime.time_scale,
        clock=runtime.clock,
    )
    game.ensure_initial_state()
    return game


def build_vehicle_catalogue(settings: Settings) -> SqliteVehicleCatalogue:
    """Resolve production PostgreSQL or an explicit local fixture."""
    if settings.database_url:
        return PostgresVehicleCatalogue(
            settings.database_url, settings.vehicle_database_schema
        )
    return SqliteVehicleCatalogue(
        settings.vehicle_catalogue_path
        or settings.base_dir / "data" / "world_freight_vehicle_catalog.sqlite3"
    )


def build_fleet_service(game: GameService, settings: Settings) -> FleetService:
    """Assemble purchasing against the authenticated player's unit of work."""
    preparation = game.market_lifecycle.preparation
    return FleetService(
        game.unit_of_work,
        build_vehicle_catalogue(settings),
        game.world,
        partial(preparation.request, changed=True) if preparation else None,
    )


def build_map_service(game: GameService) -> MapLocationService:
    """Project real catalogue locations without a network lookup."""
    return MapLocationService(game.world)


def build_traffic_reader(
    runtime: GameRuntime,
) -> TrafficReader:
    """Build the relational cross-player traffic projection."""
    return SqliteTrafficReader(runtime.database)


def build_runtime_reader(runtime: GameRuntime) -> SqliteRuntimeReader:
    """Compose lightweight reads separately from provider-owned resources."""
    return SqliteRuntimeReader(runtime.database)


def build_transport_repair(source: Path) -> TransportRepairRepository:
    """Wire explicit offline repair without opening the active game file."""
    return TransportRepairRepository(source)


def build_market_stock_upgrade(
    source: Path, now: float
) -> MarketStockUpgradeRepository:
    """Wire explicit offline schema adoption without opening active storage."""
    return MarketStockUpgradeRepository(source, now)


def build_market_stock_maintenance(
    settings: Settings,
) -> tuple[MarketStockMaintenanceService, SqliteGameDatabase]:
    """Bind explicit stock maintenance without HTTP or provider access."""
    database = build_game_database(settings)
    database.initialize()
    candidates = MarketCandidateService(
        build_world_catalogue(settings),
        CachedVehicleCatalogue(build_vehicle_catalogue(settings)),
    )
    return (
        MarketStockMaintenanceService(
            candidates,
            MarketDemandResolver(candidates),
            MarketStockMaintenanceRepository(database),
            time.time,
        ),
        database,
    )


def build_runtime_view(
    runtime: GameRuntime, user_id: str
) -> RuntimeViewService:
    """Bind compact runtime reads to authenticated game mutations."""
    return RuntimeViewService(
        build_player_service(runtime, user_id),
        build_runtime_reader(runtime),
        user_id,
    )


def build_leaderboard_reader(runtime: GameRuntime) -> LeaderboardReader:
    """Bind the public relational progress reader."""
    return SqliteLeaderboardReader(runtime.database)


def build_profile_maintenance_service(
    settings: Settings,
) -> ProfileMaintenanceService:
    """Wire local maintenance independently of the HTTP application."""
    database = SqliteGameDatabase(settings.db_path)
    database.initialize()
    accounts = AccountRepository(database)

    def player_unit_of_work_factory(user_id: str) -> SqliteGameUnitOfWork:
        """Bind the repository-verified account to its relational state."""
        return SqliteGameUnitOfWork(database, user_id)

    return ProfileMaintenanceService(
        build_vehicle_catalogue(settings),
        accounts,
        player_unit_of_work_factory,
    )


def build_world_catalogue(settings: Settings) -> CachedWorldCatalogue:
    """Resolve one lazily cached immutable runtime world revision."""
    source: WorldCatalogue
    if settings.database_url:
        source = PostgresWorldCatalogue(
            settings.database_url, settings.world_database_schema
        )
    else:
        source = SqliteWorldCatalogue(
            settings.world_catalogue_path
            or settings.base_dir
            / "data"
            / "world_freight_company_facility_mvp.sqlite3"
        )
    return CachedWorldCatalogue(source)


def build_geography_migration(
    backup: Path, target: Path
) -> GeographyMigrationStore:
    """Bind offline normalization to its immutable backup and new output."""
    return WorldGeographyRepository(backup, target)


def build_game_importer(
    source: Path, settings: Settings, exclude_global_demo: bool = False
) -> GameStateImporter:
    """Assemble the explicit offline importer without opening runtime state."""
    return LegacyGameImporter(
        source,
        WorldScope(build_world_catalogue(settings).read()),
        MarketGenerator.model_id,
        build_vehicle_catalogue(settings).list_models(),
        exclude_global_demo=exclude_global_demo,
    )


def build_energy_upgrade(
    source: Path, settings: Settings
) -> VehicleEnergyUpgradeRepository:
    """Inject catalogue snapshots into the explicit offline state upgrade."""
    return VehicleEnergyUpgradeRepository(
        source, build_vehicle_catalogue(settings).list_models()
    )


def build_market_generator(
    world: WorldCatalogue,
    rng: random.Random,
    catalogue: VehicleCatalogue,
) -> MarketGenerator:
    """Inject independent candidate, coverage and materialization services."""
    coverage = MarketCoverageService(rng)
    return MarketGenerator(
        MarketCandidateService(world, catalogue),
        coverage,
        ContractFactory(rng),
        VehicleCoverageService(coverage),
    )


def build_market_startup(runtime: GameRuntime) -> MarketStartupService:
    """Wire existing profiles to a shared outer transaction."""

    def lifecycle(user_id: str) -> MarketLifecycleService:
        """Bind market-only operations without initializing or settling."""
        preparation = build_market_preparation(runtime, user_id)
        return MarketLifecycleService(
            SqliteGameUnitOfWork(runtime.database, user_id),
            runtime.market,
            runtime.market_scope,
            runtime.clock,
            preparation,
            selection=(
                MarketSelectionService(preparation.policy)
                if preparation
                else None
            ),
        )

    return MarketStartupService(
        SqliteMarketStartupStore(runtime.database),
        runtime.world,
        runtime.catalogue,
        lifecycle,
    )


def build_preferences(runtime: GameRuntime) -> PreferenceService:
    """Assemble account cosmetics separately from game snapshots."""
    return PreferenceService(SqlitePreferenceStore(runtime.database))


def build_market_preparation(
    runtime: GameRuntime, user_id: str
) -> MarketPreparationService | None:
    """Bind production routing infrastructure to one player's offers."""
    if runtime.readiness is None or runtime.preparation_jobs is None:
        return None
    templates = runtime.template_store or SqliteMarketTemplateStore(
        runtime.database
    )
    return MarketPreparationService(
        user_id,
        runtime.readiness,
        SqliteOfferRouteStore(runtime.database, user_id),
        runtime.preparation_jobs,
        runtime.clock,
        runtime.database,
        SqliteMarketStockStore(runtime.database, user_id, templates),
    )


def build_preparation_worker(runtime: GameRuntime) -> MarketPreparationWorker:
    """Assemble owned preparation without initializing player state."""
    assert runtime.preparation_jobs is not None
    assert runtime.readiness is not None
    templates = runtime.template_store or SqliteMarketTemplateStore(
        runtime.database
    )
    lease = PreparationLease(runtime.readiness.store, runtime.clock)
    runtime.readiness.worker_owner = lease.owner

    def batch(user_id: str) -> StockPreparationBatch:
        """Compose one player's preparation without changing state."""
        preparation = build_market_preparation(runtime, user_id)
        assert preparation is not None
        return StockPreparationBatch(
            StockPublicationService(
                SqliteGameUnitOfWork(runtime.database, user_id),
                runtime.market,
                preparation,
                MarketDemandResolver(runtime.market.candidates),
                lease.owned,
            ),
            StockPlanningService(preparation.policy),
            MarketTemplateService(
                runtime.market.factory, preparation.policy, runtime.clock
            ),
        )

    stock_policy = StockPolicy()
    global_batch = GlobalStockPreparationBatch(
        runtime.market.candidates,
        MarketDemandResolver(runtime.market.candidates),
        StockPlanningService(stock_policy),
        MarketTemplateService(
            runtime.market.factory, stock_policy, runtime.clock
        ),
        runtime.readiness,
        templates,
        runtime.database,
        runtime.clock,
        lease.owned,
    )
    return MarketPreparationWorker(
        runtime.preparation_jobs,
        batch,
        runtime.clock,
        lease,
        global_batch,
    )


def build_routing_audit(runtime: GameRuntime) -> SqliteRoutingAudit:
    """Compose local routing diagnostics without provider operations."""
    return SqliteRoutingAudit(runtime.database)


def build_economy_audit(root: Path, seed: int) -> EconomyAuditService:
    """Compose reproducible audits from explicit offline catalogues."""
    return EconomyAuditService(
        SqliteVehicleCatalogue(
            root / "data/world_freight_vehicle_catalog.sqlite3"
        ),
        SqliteWorldCatalogue(
            root / "data/world_freight_company_facility_mvp.sqlite3"
        ),
        random.Random(seed),
    )
