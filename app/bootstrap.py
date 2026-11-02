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
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.read_ports import LeaderboardReader, TrafficReader
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
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_stock_repair import SqliteMarketStockRepairStore
from app.repositories.market_stock_upgrade import MarketStockUpgradeRepository
from app.repositories.market_templates import SqliteMarketTemplateStore
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
from app.services.economy_audit import EconomyAuditService
from app.services.gameplay.dispatch import TransportDispatchService
from app.services.gameplay.dispatch_eligibility import (
    DispatchEligibilityService,
)
from app.services.gameplay.dispatch_planning import DispatchPlanningService
from app.services.gameplay.fleet import FleetService
from app.services.gameplay.game import GameService
from app.services.gameplay.initialization import PlayerInitializationService
from app.services.gameplay.settlement import TransportSettlementService
from app.services.gameplay.vehicle_costs import VehicleCostResolver
from app.services.gameplay.vehicle_location import VehicleLocationResolver
from app.services.map_locations import MapLocationService
from app.services.market.candidates import MarketCandidateService
from app.services.market.components import MarketComponents
from app.services.market.contract_factory import ContractFactory
from app.services.market.demand import MarketDemandResolver
from app.services.market.lifecycle import MarketLifecycleService
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_services import PlayerMarketServices
from app.services.market.player_stock import PlayerMarketStockContext
from app.services.market.route_preparation import (
    MarketRoutePreparationService,
)
from app.services.market.scope import MarketScopeResolver
from app.services.market.selection import MarketSelectionService
from app.services.market.stock.maintenance import (
    MarketStockRepairPlanner,
    MarketStockRepairService,
)
from app.services.market.stock.planning import StockPlanningService
from app.services.market.stock.preparation import StockPreparationBatch
from app.services.market.stock.publication import StockPublicationService
from app.services.market.stock.snapshot import StockSnapshotReader
from app.services.market.templates import MarketTemplateService
from app.services.market.vehicle_coverage import VehicleCoverageService
from app.services.market.worker import MarketPreparationWorker
from app.services.preferences import PreferenceService
from app.services.profile_maintenance import ProfileMaintenanceService
from app.services.routing.anchors import RoutingAnchorResolver
from app.services.routing.evidence import RoutingEvidenceReader
from app.services.routing.preparation import RoutingPreparationService
from app.services.runtime_views import RuntimeViewService


@dataclass
class GameRuntime:
    """Shared dependencies owned by the application composition root."""

    database: SqliteGameDatabase
    world: WorldCatalogue
    market: MarketComponents
    catalogue: VehicleCatalogue
    market_scope: MarketScopeResolver
    routing_evidence: RoutingEvidenceReader
    routing_preparation: RoutingPreparationService
    preparation_jobs: SqlitePreparationStore
    time_scale: float
    clock: Callable[[], float] = time.time


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


def build_game_runtime(
    settings: Settings,
    routing_client: httpx.AsyncClient,
    rng_seed: int | None = None,
    clock: Callable[[], float] = time.time,
) -> GameRuntime:
    """Initialize only relational storage and shared application resources."""
    database = SqliteGameDatabase(settings.db_path)
    database.initialize()
    cache = SqliteProviderCache(database)
    evidence = SqliteRoutingReadinessStore(database)
    jobs = SqlitePreparationStore(database)
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
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
    anchors = build_routing_anchor_resolver(
        database, settings, routing_client, clock, limiter, evidence
    )
    routing_evidence = RoutingEvidenceReader(
        evidence,
        SqliteRoutingAnchorRepository(database),
        world,
        settings.valhalla_url,
        clock,
        anchors.max_snap_distance_m,
        provider_revision=partial(
            evidence.provider_revision, settings.valhalla_url
        ),
    )
    routing_preparation = RoutingPreparationService(
        routing_evidence,
        evidence,
        anchors,
        router,
        world,
        clock,
    )
    return GameRuntime(
        routing_evidence=routing_evidence,
        routing_preparation=routing_preparation,
        preparation_jobs=jobs,
        database=database,
        world=world,
        market=build_market_components(
            world, random.Random(rng_seed), catalogue
        ),
        catalogue=catalogue,
        market_scope=MarketScopeResolver(world),
        time_scale=settings.game_time_scale,
        clock=clock,
    )


def build_player_service(runtime: GameRuntime, user_id: str) -> GameService:
    """Bind one authenticated owner to the shared relational transaction."""
    market_services = build_player_market_services(runtime, user_id)
    unit = SqliteGameUnitOfWork(runtime.database, user_id)
    lifecycle = MarketLifecycleService(
        unit,
        runtime.market,
        runtime.market_scope,
        runtime.clock,
        market_services.demand,
        market_services.routes,
        market_services.stock,
        selection=MarketSelectionService(market_services.stock.policy),
    )
    planning = DispatchPlanningService(
        VehicleCostResolver(runtime.catalogue),
        market_services.routes,
    )
    settlement = TransportSettlementService(
        unit,
        runtime.clock,
        market_services.demand,
    )
    dispatch = TransportDispatchService(
        unit,
        runtime.market,
        planning,
        DispatchEligibilityService(runtime.market.candidates),
        VehicleLocationResolver(runtime.world),
        settlement,
        runtime.clock,
        runtime.time_scale,
        market_services.demand,
        market_services.stock,
    )
    game = GameService(
        unit,
        runtime.clock,
        runtime.time_scale,
        lifecycle,
        PlayerInitializationService(
            unit,
            runtime.world,
            runtime.catalogue,
            market_services.demand,
        ),
        settlement,
        dispatch,
        market_services,
    )
    game.ensure_initial_state()
    return game


def build_vehicle_catalogue(settings: Settings) -> SqliteVehicleCatalogue:
    """Resolve the bundled catalogue independently of the player database."""
    return SqliteVehicleCatalogue(
        settings.vehicle_catalogue_path
        or settings.base_dir / "data" / "world_freight_vehicle_catalog.sqlite3"
    )


def build_fleet_service(
    runtime: GameRuntime,
    game: GameService,
) -> FleetService:
    """Assemble purchasing against the authenticated player's unit of work."""
    return FleetService(
        game.unit_of_work,
        runtime.catalogue,
        runtime.world,
        game.market_services.demand.invalidate,
    )


def build_map_service(runtime: GameRuntime) -> MapLocationService:
    """Project real catalogue locations without a network lookup."""
    return MapLocationService(runtime.world)


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


def build_market_stock_repair(source: Path) -> MarketStockRepairService:
    """Wire read-only historical stock inspection outside the runtime."""
    policy = StockPolicy()
    return MarketStockRepairService(
        SqliteMarketStockRepairStore(source),
        MarketStockRepairPlanner(
            policy,
            MarketSelectionService(policy),
        ),
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
        MarketComponents.model_id,
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


def build_market_components(
    world: WorldCatalogue,
    rng: random.Random,
    catalogue: VehicleCatalogue,
) -> MarketComponents:
    """Bundle independent candidate, materialization and coverage services."""
    return MarketComponents(
        MarketCandidateService(world, catalogue),
        ContractFactory(rng),
        VehicleCoverageService(),
    )


def build_preferences(runtime: GameRuntime) -> PreferenceService:
    """Assemble account cosmetics separately from game snapshots."""
    return PreferenceService(SqlitePreferenceStore(runtime.database))


def build_player_market_services(
    runtime: GameRuntime, user_id: str
) -> PlayerMarketServices:
    """Bind production routing infrastructure to one player's offers."""
    return PlayerMarketServices(
        PlayerMarketDemandService(
            user_id,
            runtime.preparation_jobs,
            runtime.clock,
            runtime.database,
        ),
        PlayerMarketRouteService(
            runtime.routing_evidence,
            SqliteOfferRouteStore(runtime.database, user_id),
            runtime.database,
        ),
        MarketRoutePreparationService(
            runtime.routing_evidence,
            runtime.routing_preparation,
            runtime.clock,
        ),
        PlayerMarketStockContext(
            SqlitePlayerMarketStockStore(runtime.database, user_id),
            SqliteMarketTemplateStore(runtime.database),
        ),
    )


def build_preparation_worker(runtime: GameRuntime) -> MarketPreparationWorker:
    """Assemble owned preparation without initializing player state."""

    def batch(user_id: str) -> StockPreparationBatch:
        """Compose one player's preparation without changing state."""
        market_services = build_player_market_services(runtime, user_id)
        unit = SqliteGameUnitOfWork(runtime.database, user_id)
        demand = MarketDemandResolver(runtime.market.candidates)
        return StockPreparationBatch(
            StockPublicationService(
                unit,
                runtime.market,
                market_services.demand,
                market_services.routes,
                market_services.stock,
                lambda: True,
            ),
            StockSnapshotReader(
                unit,
                runtime.market,
                market_services.demand,
                market_services.routes,
                market_services.stock,
                demand,
            ),
            StockPlanningService(market_services.stock.policy),
            MarketTemplateService(
                runtime.market.factory,
                market_services.stock.policy,
                runtime.clock,
            ),
            market_services.route_preparation,
        )

    worker = MarketPreparationWorker(
        runtime.preparation_jobs,
        batch,
        runtime.clock,
    )
    runtime.preparation_jobs.set_notifier(worker.wake)
    return worker


def build_routing_audit(runtime: GameRuntime) -> SqliteRoutingAudit:
    """Compose local routing diagnostics without provider operations."""
    return SqliteRoutingAudit(runtime.database)


def build_economy_audit(root: Path, seed: int) -> EconomyAuditService:
    """Compose reproducible audits from read-only reference catalogues."""
    return EconomyAuditService(
        SqliteVehicleCatalogue(
            root / "data/world_freight_vehicle_catalog.sqlite3"
        ),
        SqliteWorldCatalogue(
            root / "data/world_freight_company_facility_mvp.sqlite3"
        ),
        random.Random(seed),
    )
