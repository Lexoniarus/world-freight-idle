from __future__ import annotations

import random
import time
from pathlib import Path

import pytest

from app.bootstrap import GameRuntime, build_market_components
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.services.cost_profiles import VehicleCostResolver
from app.services.dispatch_eligibility import DispatchEligibilityService
from app.services.dispatch_planning import DispatchPlanningService
from app.services.game import GameService
from app.services.market_lifecycle import MarketLifecycleService
from app.services.market_scope import MarketScopeResolver
from app.services.player_initialization import PlayerInitializationService
from app.services.transport_dispatch import TransportDispatchService
from app.services.transport_settlement import TransportSettlementService
from app.services.vehicle_location import VehicleLocationResolver
from tests.support.catalogues import WORLD_PATH
from tests.support.game import create_active_trip
from tests.support.market import seed_test_offers
from tests.support.market_fixtures import (
    city_market as city_market,
)
from tests.support.market_fixtures import (
    vehicle_game as vehicle_game,
)
from tests.support.persistence_fixtures import relational as relational
from tests.support.routing import FakeRouter, FakeRoutingAnchorResolver


@pytest.fixture
def cache(database) -> SqliteProviderCache:
    return SqliteProviderCache(database)


@pytest.fixture
def active_trip(game):
    """Persist one active transport for tests that require runtime state."""
    return create_active_trip(game)


@pytest.fixture
def world_catalogue(tmp_path):
    import shutil

    path = tmp_path / "world.sqlite3"
    shutil.copyfile(WORLD_PATH, path)
    return SqliteWorldCatalogue(path)


@pytest.fixture
def game(database, catalogue, world_catalogue) -> GameService:
    market = build_market_components(
        world_catalogue, random.Random(7), catalogue
    )
    router = FakeRouter()
    anchors = FakeRoutingAnchorResolver()
    unit = SqliteGameUnitOfWork(database, "test-owner")
    scope = MarketScopeResolver(world_catalogue)
    lifecycle = MarketLifecycleService(unit, market, scope, time.time)
    planning = DispatchPlanningService(
        router,
        VehicleCostResolver(catalogue),
        anchors,
        world_catalogue,
    )
    settlement = TransportSettlementService(
        unit,
        time.time,
        None,
        lifecycle.refill_after_commit,
    )
    dispatch = TransportDispatchService(
        unit,
        market,
        planning,
        DispatchEligibilityService(market.candidates),
        VehicleLocationResolver(world_catalogue),
        settlement,
        time.time,
        1.0,
        lifecycle.prune_in_transaction,
        lifecycle.refill_after_commit,
    )
    service = GameService(
        unit,
        world_catalogue,
        market,
        catalogue,
        scope,
        time.time,
        1.0,
        lifecycle,
        PlayerInitializationService(unit, world_catalogue, catalogue),
        settlement,
        dispatch,
    )
    service.ensure_initial_state()
    seed_test_offers(service)
    return service


@pytest.fixture
def catalogue(tmp_path):
    import shutil

    from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue

    path = tmp_path / "catalogue.sqlite3"
    shutil.copyfile(
        Path(__file__).resolve().parents[1]
        / "data"
        / "world_freight_vehicle_catalog.sqlite3",
        path,
    )
    return SqliteVehicleCatalogue(path)


@pytest.fixture
def database(tmp_path):
    database = SqliteGameDatabase(tmp_path / "relational.db")
    database.initialize()
    from app.repositories.preferences import SqlitePreferenceStore

    SqlitePreferenceStore(database)
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES ('test-owner', 'TestOwner', 'test', 0)"
        )
    return database


@pytest.fixture
def runtime(game, database):
    return GameRuntime(
        database,
        game.world,
        game.transport_dispatch.planning.router,
        game.transport_dispatch.planning.anchors,
        game.market,
        game.catalogue,
        game.market_scope,
        game.time_scale,
    )
