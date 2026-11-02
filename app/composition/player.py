"""Authenticated player and background-market dependency assembly."""

from app.composition.runtime import GameRuntime
from app.domain.read_ports import LeaderboardReader, TrafficReader
from app.repositories.analytics import SqliteAnalyticsReader
from app.repositories.game_state import SqliteGameUnitOfWork
from app.repositories.leaderboard import SqliteLeaderboardReader
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.repositories.preferences import SqlitePreferenceStore
from app.repositories.relational_traffic import SqliteTrafficReader
from app.repositories.routing_readiness import SqliteOfferRouteStore
from app.repositories.runtime_views import SqliteRuntimeReader
from app.services.analytics import AnalyticsService
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
from app.services.market.demand import MarketDemandResolver
from app.services.market.lifecycle import MarketLifecycleService
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_services import PlayerMarketServices
from app.services.market.player_stores import PlayerMarketStores
from app.services.market.route_preparation import MarketRoutePreparationService
from app.services.market.selection import MarketSelectionService
from app.services.market.stock.planning import StockPlanningService
from app.services.market.stock.preparation import StockPreparationBatch
from app.services.market.stock.publication import StockPublicationService
from app.services.market.stock.snapshot import StockSnapshotReader
from app.services.market.templates import MarketTemplateService
from app.services.market.worker import MarketPreparationWorker
from app.services.preferences import PreferenceService
from app.services.runtime_views import RuntimeViewService


def build_analytics_service(
    runtime: GameRuntime, user_id: str
) -> AnalyticsService:
    """Bind private analytics to an authenticated account."""
    return AnalyticsService(SqliteAnalyticsReader(runtime.database, user_id))


def build_player_service(runtime: GameRuntime, user_id: str) -> GameService:
    """Bind one authenticated owner to the shared relational transaction."""
    player_market = build_player_market_services(runtime, user_id)
    unit = SqliteGameUnitOfWork(runtime.database, user_id)
    lifecycle = MarketLifecycleService(
        unit,
        runtime.market_generation,
        runtime.market_scope,
        runtime.clock,
        player_market.demand,
        player_market.routes,
        player_market.stores,
        selection=MarketSelectionService(player_market.stores.policy),
    )
    planning = DispatchPlanningService(
        VehicleCostResolver(runtime.catalogue),
        player_market.routes,
    )
    settlement = TransportSettlementService(
        unit,
        runtime.clock,
        player_market.demand,
    )
    dispatch = TransportDispatchService(
        unit,
        runtime.market_generation,
        planning,
        DispatchEligibilityService(runtime.market_generation.candidates),
        VehicleLocationResolver(runtime.world),
        settlement,
        runtime.clock,
        runtime.time_scale,
        player_market.demand,
        player_market.stores,
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
            player_market.demand,
        ),
        settlement,
        dispatch,
        player_market,
    )
    game.ensure_initial_state()
    return game


def build_fleet_service(
    runtime: GameRuntime,
    game: GameService,
) -> FleetService:
    """Assemble purchasing against the authenticated player's unit of work."""
    return FleetService(
        game.unit_of_work,
        runtime.catalogue,
        runtime.world,
        game.player_market.demand.invalidate,
    )


def build_map_service(runtime: GameRuntime) -> MapLocationService:
    """Project real catalogue locations without a network lookup."""
    return MapLocationService(runtime.world)


def build_traffic_reader(runtime: GameRuntime) -> TrafficReader:
    """Build the relational cross-player traffic projection."""
    return SqliteTrafficReader(runtime.database)


def build_runtime_reader(runtime: GameRuntime) -> SqliteRuntimeReader:
    """Compose lightweight reads separately from provider-owned resources."""
    return SqliteRuntimeReader(runtime.database)


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
        PlayerMarketStores(
            SqlitePlayerMarketStockStore(runtime.database, user_id),
            SqliteMarketTemplateStore(runtime.database),
        ),
    )


def build_preparation_worker(runtime: GameRuntime) -> MarketPreparationWorker:
    """Assemble owned preparation without initializing player state."""

    def batch(user_id: str) -> StockPreparationBatch:
        """Compose one player's preparation without changing state."""
        player_market = build_player_market_services(runtime, user_id)
        unit = SqliteGameUnitOfWork(runtime.database, user_id)
        demand = MarketDemandResolver(runtime.market_generation.candidates)
        return StockPreparationBatch(
            StockPublicationService(
                unit,
                runtime.market_generation,
                player_market.demand,
                player_market.routes,
                player_market.stores,
                lambda: True,
            ),
            StockSnapshotReader(
                unit,
                runtime.market_generation,
                player_market.demand,
                player_market.routes,
                player_market.stores,
                demand,
            ),
            StockPlanningService(player_market.stores.policy),
            MarketTemplateService(
                runtime.market_generation.contract_factory,
                player_market.stores.policy,
                runtime.clock,
            ),
            player_market.route_preparation,
        )

    worker = MarketPreparationWorker(
        runtime.preparation_jobs,
        batch,
        runtime.clock,
    )
    runtime.preparation_jobs.set_notifier(worker.wake)
    return worker
