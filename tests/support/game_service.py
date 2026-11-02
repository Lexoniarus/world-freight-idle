"""Explicit production-shaped player composition for local tests."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from app.composition.player import PlayerContextFactory
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.state_ports import GameStateRepository
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.services.gameplay.dispatch import TransportDispatchService
from app.services.gameplay.initialization import PlayerInitializationService
from app.services.gameplay.player_game import PlayerGameFacade
from app.services.gameplay.settlement import TransportSettlementService
from app.services.market.generation_services import MarketGenerationServices
from app.services.market.lifecycle import MarketLifecycleService
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_services import PlayerMarketServices
from app.services.market.player_stores import PlayerMarketStores
from app.services.market.route_preparation import MarketRoutePreparationService
from app.services.market.scope import MarketScopeResolver
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


class FixturePlayerGameFacade(PlayerGameFacade):
    """Expose injected collaborators only inside explicit test composition."""

    @property
    def unit_of_work(self) -> SqliteGameUnitOfWork:
        """Return the fixture transaction boundary for failure injection."""
        return cast(SqliteGameUnitOfWork, self._unit_of_work)

    @property
    def state_repository(self) -> GameStateRepository:
        """Return fixture persistence for repository-level assertions."""
        return self._state_repository

    @property
    def market_lifecycle(self) -> MarketLifecycleService:
        """Return the fixture market lifecycle for focused service tests."""
        return self._market_lifecycle

    @property
    def initialization(self) -> PlayerInitializationService:
        """Return the fixture initialization workflow."""
        return self._initialization

    @property
    def settlement(self) -> TransportSettlementService:
        """Return the fixture settlement workflow."""
        return self._settlement

    @property
    def transport_dispatch(self) -> TransportDispatchService:
        """Return the fixture dispatch workflow."""
        return self._transport_dispatch

    @property
    def player_market(self) -> PlayerMarketServices:
        """Return the fixture market collaborators."""
        return self._player_market


@dataclass(frozen=True, slots=True)
class FixtureGameContext:
    """Keep test-only collaborators outside the production game facade."""

    service: FixturePlayerGameFacade
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
    context = PlayerContextFactory(
        unit,
        world,
        synthetic_vehicle_catalogue,
        market_generation,
        scope,
        player_market,
        clock,
        time_scale,
    ).create(FixturePlayerGameFacade)
    service = cast(FixturePlayerGameFacade, context.game)
    return FixtureGameContext(
        service,
        world,
        synthetic_vehicle_catalogue,
        market_generation,
        scope,
    )
