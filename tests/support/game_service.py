"""Explicit production-shaped player composition for local tests."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.services.gameplay.dispatch import TransportDispatchService
from app.services.gameplay.dispatch_eligibility import (
    DispatchEligibilityService,
)
from app.services.gameplay.dispatch_planning import DispatchPlanningService
from app.services.gameplay.game import GameService
from app.services.gameplay.initialization import PlayerInitializationService
from app.services.gameplay.settlement import TransportSettlementService
from app.services.gameplay.vehicle_costs import VehicleCostResolver
from app.services.gameplay.vehicle_location import VehicleLocationResolver
from app.services.market.generation_services import MarketGenerationServices
from app.services.market.lifecycle import MarketLifecycleService
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_services import PlayerMarketServices
from app.services.market.player_stores import PlayerMarketStores
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


@dataclass(frozen=True, slots=True)
class FixtureGameContext:
    """Keep test-only collaborators outside the production game facade."""

    service: GameService
    world: WorldCatalogue
    catalogue: VehicleCatalogue
    market_generation: MarketGenerationServices
    market_scope: MarketScopeResolver


def build_fixture_game(
    database: SqliteGameDatabase,
    user_id: str,
    world: WorldCatalogue,
    synthetic_vehicle_catalogue: VehicleCatalogue,
    market_generation: MarketGenerationServices,
    clock: Callable[[], float],
    time_scale: float = 1.0,
) -> FixtureGameContext:
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
    player_market = PlayerMarketServices(
        PlayerMarketDemandService(user_id, jobs, clock, database),
        PlayerMarketRouteService(
            readiness,
            MemoryOfferRouteStore(),
            database,
        ),
        MarketRoutePreparationService(readiness, preparation, clock),
        PlayerMarketStores(
            MemoryPlayerMarketStockStore(),
            MemoryMarketTemplateStore(),
        ),
    )
    lifecycle = MarketLifecycleService(
        unit,
        market_generation,
        scope,
        clock,
        player_market.demand,
        player_market.routes,
        player_market.stores,
        MarketSelectionService(player_market.stores.policy),
    )
    planning = DispatchPlanningService(
        VehicleCostResolver(synthetic_vehicle_catalogue),
        player_market.routes,
    )
    settlement = TransportSettlementService(
        unit,
        clock,
        player_market.demand,
    )
    dispatch = TransportDispatchService(
        unit,
        market_generation,
        planning,
        DispatchEligibilityService(market_generation.candidates),
        VehicleLocationResolver(world),
        settlement,
        clock,
        time_scale,
        player_market.demand,
        player_market.stores,
    )
    service = GameService(
        unit,
        clock,
        time_scale,
        lifecycle,
        PlayerInitializationService(
            unit,
            world,
            synthetic_vehicle_catalogue,
            player_market.demand,
        ),
        settlement,
        dispatch,
        player_market,
    )
    return FixtureGameContext(
        service,
        world,
        synthetic_vehicle_catalogue,
        market_generation,
        scope,
    )
