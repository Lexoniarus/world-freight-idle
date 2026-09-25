from __future__ import annotations

import random
import time
from pathlib import Path

import pytest

from app.bootstrap import GameRuntime, build_market_generator
from app.domain.transports import RouteSnapshot
from app.domain.world_scopes import WorldScope
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.services.cost_profiles import VehicleCostResolver
from app.services.dispatch_planning import DispatchPlanningService
from app.services.game import GameService
from app.services.market_scope import MarketScopeResolver


class FakeRouter:
    async def route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteSnapshot:
        return RouteSnapshot(
            distance_km=400.0,
            duration_seconds=14400.0,
            coordinates=(
                (origin_lon, origin_lat),
                (destination_lon, destination_lat),
            ),
            provider="fake-router",
        )


@pytest.fixture
def cache(database) -> SqliteProviderCache:
    return SqliteProviderCache(database)


WORLD_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "world_freight_company_facility_mvp.sqlite3"
)
BERLIN_UID = (
    WorldScope(SqliteWorldCatalogue(WORLD_PATH).read())
    .facility("berlin_westhafen")
    .facility_uid
)


@pytest.fixture
def world_catalogue(tmp_path):
    import shutil

    path = tmp_path / "world.sqlite3"
    shutil.copyfile(WORLD_PATH, path)
    return SqliteWorldCatalogue(path)


@pytest.fixture
def game(database, catalogue, world_catalogue) -> GameService:
    market = build_market_generator(
        world_catalogue, random.Random(7), catalogue
    )
    service = GameService(
        unit_of_work=SqliteGameUnitOfWork(database, "test-owner"),
        world=world_catalogue,
        router=(router := FakeRouter()),
        dispatch_planning=DispatchPlanningService(
            router, VehicleCostResolver(catalogue)
        ),
        market=market,
        market_scope=MarketScopeResolver(world_catalogue),
        catalogue=catalogue,
        time_scale=1.0,
        clock=time.time,
    )
    service.ensure_initial_state()
    service.refresh_market(force=True)
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
        game.router,
        game.market,
        game.catalogue,
        game.market_scope,
        game.time_scale,
    )
