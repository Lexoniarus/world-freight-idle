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
from app.services.market_components import MarketComponents
from app.services.market_lifecycle import MarketLifecycleService
from app.services.market_route_preparation import MarketRoutePreparationService
from app.services.market_scope import MarketScopeResolver
from app.services.market_selection import MarketSelectionService
from app.services.player_market_demand import PlayerMarketDemandService
from app.services.player_market_routes import PlayerMarketRouteService
from app.services.player_market_services import PlayerMarketServices
from app.services.player_market_stock import PlayerMarketStockContext
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
    catalogue: VehicleCatalogue,
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
        VehicleCostResolver(catalogue),
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
        catalogue,
        scope,
        clock,
        time_scale,
        lifecycle,
        PlayerInitializationService(
            unit,
            world,
            catalogue,
            market_services.demand,
        ),
        settlement,
        dispatch,
        market_services,
    )
