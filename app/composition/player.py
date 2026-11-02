"""Authenticated player and background-market dependency assembly."""

from collections.abc import Callable
from dataclasses import dataclass

from app.composition.runtime import GameRuntime
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.read_ports import LeaderboardReader, TrafficReader
from app.domain.state_ports import GameStateRepository
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
from app.services.gameplay.initialization import PlayerInitializationService
from app.services.gameplay.player_game import PlayerGameFacade
from app.services.gameplay.settlement import TransportSettlementService
from app.services.gameplay.vehicle_costs import VehicleCostResolver
from app.services.gameplay.vehicle_location import VehicleLocationResolver
from app.services.map_locations import MapLocationService
from app.services.market.demand import MarketDemandResolver
from app.services.market.generation_services import MarketGenerationServices
from app.services.market.lifecycle import MarketLifecycleService
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_services import PlayerMarketServices
from app.services.market.player_stores import PlayerMarketStores
from app.services.market.route_preparation import MarketRoutePreparationService
from app.services.market.scope import MarketScopeResolver
from app.services.market.selection import MarketSelectionService
from app.services.market.stock.planning import StockPlanningService
from app.services.market.stock.preparation import StockPreparationBatch
from app.services.market.stock.publication import StockPublicationService
from app.services.market.stock.snapshot import StockSnapshotReader
from app.services.market.templates import MarketTemplateService
from app.services.market.worker import MarketPreparationWorker
from app.services.preferences import PreferenceService
from app.services.runtime_views import RuntimeViewService


@dataclass(frozen=True, slots=True)
class PlayerServiceContext:
    """Keep composition collaborators outside the public player facade."""

    game: PlayerGameFacade
    unit_of_work: SqliteGameUnitOfWork
    state_repository: GameStateRepository
    market: PlayerMarketServices
    lifecycle: MarketLifecycleService
    initialization: PlayerInitializationService
    settlement: TransportSettlementService
    dispatch: TransportDispatchService


@dataclass(frozen=True, slots=True)
class PlayerContextFactory:
    """Compose one player from injected runtime and adapter boundaries."""

    unit_of_work: SqliteGameUnitOfWork
    world: WorldCatalogue
    catalogue: VehicleCatalogue
    market_generation: MarketGenerationServices
    market_scope: MarketScopeResolver
    market: PlayerMarketServices
    clock: Callable[[], float]
    time_scale: float

    def create(
        self,
        facade_type: type[PlayerGameFacade] = PlayerGameFacade,
    ) -> PlayerServiceContext:
        """Build the shared workflow graph with the requested facade type."""
        lifecycle = MarketLifecycleService(
            self.unit_of_work,
            self.market_generation,
            self.market_scope,
            self.clock,
            self.market.demand,
            self.market.routes,
            self.market.stores,
            selection=MarketSelectionService(self.market.stores.policy),
        )
        planning = DispatchPlanningService(
            VehicleCostResolver(self.catalogue),
            self.market.routes,
        )
        settlement = TransportSettlementService(
            self.unit_of_work,
            self.clock,
            self.market.demand,
        )
        dispatch = TransportDispatchService(
            self.unit_of_work,
            self.market_generation,
            planning,
            DispatchEligibilityService(self.market_generation.candidates),
            VehicleLocationResolver(self.world),
            settlement,
            self.clock,
            self.time_scale,
            self.market.demand,
            self.market.stores,
        )
        initialization = PlayerInitializationService(
            self.unit_of_work,
            self.world,
            self.catalogue,
            self.market.demand,
        )
        game = facade_type(
            self.unit_of_work,
            self.clock,
            self.time_scale,
            lifecycle,
            initialization,
            settlement,
            dispatch,
            self.market,
        )
        return PlayerServiceContext(
            game,
            self.unit_of_work,
            self.unit_of_work.repository,
            self.market,
            lifecycle,
            initialization,
            settlement,
            dispatch,
        )


def build_analytics_service(
    runtime: GameRuntime, user_id: str
) -> AnalyticsService:
    """Bind private analytics to an authenticated account."""
    return AnalyticsService(SqliteAnalyticsReader(runtime.database, user_id))


def build_player_context(
    runtime: GameRuntime, user_id: str
) -> PlayerServiceContext:
    """Compose one player and retain collaborators at the composition edge."""
    player_market = build_player_market_services(runtime, user_id)
    unit = SqliteGameUnitOfWork(runtime.database, user_id)
    context = PlayerContextFactory(
        unit,
        runtime.world,
        runtime.catalogue,
        runtime.market_generation,
        runtime.market_scope,
        player_market,
        runtime.clock,
        runtime.time_scale,
    ).create()
    context.game.ensure_initial_state()
    return context


def build_player_service(
    runtime: GameRuntime, user_id: str
) -> PlayerGameFacade:
    """Return only the public player facade for ordinary consumers."""
    return build_player_context(runtime, user_id).game


def build_fleet_service(
    runtime: GameRuntime,
    context: PlayerServiceContext,
) -> FleetService:
    """Assemble purchasing against the authenticated player's unit of work."""
    return FleetService(
        context.unit_of_work,
        runtime.catalogue,
        runtime.world,
        context.market.demand.invalidate,
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
