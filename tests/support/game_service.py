"""Explicit production-shaped player composition for local tests."""

from collections.abc import Callable
from typing import cast

from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.services.cost_profiles import VehicleCostResolver
from app.services.gameplay.dispatch import TransportDispatchService
from app.services.gameplay.dispatch_eligibility import (
    DispatchEligibilityService,
)
from app.services.gameplay.dispatch_planning import DispatchPlanningService
from app.services.gameplay.game import GameService
from app.services.gameplay.initialization import PlayerInitializationService
from app.services.gameplay.settlement import TransportSettlementService
from app.services.gameplay.vehicle_location import VehicleLocationResolver
from app.services.market.components import MarketComponents
from app.services.market.lifecycle import MarketLifecycleService
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_services import PlayerMarketServices
from app.services.market.player_stock import PlayerMarketStockContext
from app.services.market.route_preparation import MarketRoutePreparationService
from app.services.market.scope import MarketScopeResolver
from app.services.market.selection import MarketSelectionService
from app.services.routing.evidence import RoutingEvidenceReader
from app.services.routing.preparation import RoutingPreparationService
from tests.support.market_state import (
    FixturePreparationStore,
    MemoryMarketTemplateStore,
    MemoryPlayerMarketStockStore,
)
from tests.support.routing import (
    FixtureRoutingPreparation,
    FixtureRoutingReadiness,
    MemoryOfferRouteStore,
)


def build_fixture_game(
    database: SqliteGameDatabase,
    user_id: str,
    world: WorldCatalogue,
    synthetic_vehicle_catalogue: VehicleCatalogue,
    market: MarketComponents,
    clock: Callable[[], float],
    time_scale: float = 1.0,
) -> GameService:
    """Compose every mandatory player dependency without provider access."""
    jobs = FixturePreparationStore()
    fixture_evidence = FixtureRoutingReadiness(world, clock)
    readiness = cast(RoutingEvidenceReader, fixture_evidence)
    preparation = cast(
        RoutingPreparationService,
        FixtureRoutingPreparation(fixture_evidence),
    )
    unit = SqliteGameUnitOfWork(database, user_id)
    scope = MarketScopeResolver(world)
    market_services = PlayerMarketServices(
        PlayerMarketDemandService(user_id, jobs, clock, database),
        PlayerMarketRouteService(
            readiness,
            MemoryOfferRouteStore(),
            database,
        ),
        MarketRoutePreparationService(readiness, preparation, clock),
        PlayerMarketStockContext(
            MemoryPlayerMarketStockStore(),
            MemoryMarketTemplateStore(),
        ),
    )
    lifecycle = MarketLifecycleService(
        unit,
        market,
        scope,
        clock,
        market_services.demand,
        market_services.routes,
        market_services.stock,
        MarketSelectionService(market_services.stock.policy),
    )
    planning = DispatchPlanningService(
        VehicleCostResolver(synthetic_vehicle_catalogue),
        market_services.routes,
    )
    settlement = TransportSettlementService(
        unit,
        clock,
        market_services.demand,
    )
    dispatch = TransportDispatchService(
        unit,
        market,
        planning,
        DispatchEligibilityService(market.candidates),
        VehicleLocationResolver(world),
        settlement,
        clock,
        time_scale,
        market_services.demand,
        market_services.stock,
    )
    return GameService(
        unit,
        world,
        market,
        synthetic_vehicle_catalogue,
        scope,
        clock,
        time_scale,
        lifecycle,
        PlayerInitializationService(
            unit,
            world,
            synthetic_vehicle_catalogue,
            market_services.demand,
        ),
        settlement,
        dispatch,
        market_services,
    )
