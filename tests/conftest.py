from __future__ import annotations

import random
import time

import pytest

from app.bootstrap import build_market_components
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.services.gameplay.game import GameService
from tests.support.catalogues import (
    REFERENCE_VEHICLE_PATH,
    REFERENCE_WORLD_PATH,
    build_synthetic_vehicle_catalogue,
    build_synthetic_world_catalogue,
)
from tests.support.game import create_active_trip
from tests.support.game_service import build_fixture_game
from tests.support.legacy_fixtures import legacy_source as legacy_source
from tests.support.market import seed_test_offers
from tests.support.market_fixtures import (
    city_market as city_market,
)
from tests.support.market_fixtures import (
    vehicle_game as vehicle_game,
)
from tests.support.persistence_fixtures import relational as relational
from tests.support.runtime import build_test_runtime


@pytest.fixture
def cache(database) -> SqliteProviderCache:
    return SqliteProviderCache(database)


@pytest.fixture
def active_trip(synthetic_game):
    """Persist one active transport for tests that require runtime state."""
    return create_active_trip(synthetic_game)


@pytest.fixture
def reference_world_catalogue(tmp_path):
    """Copy the packaged world only for repository acceptance tests."""
    import shutil

    path = tmp_path / "world.sqlite3"
    shutil.copyfile(REFERENCE_WORLD_PATH, path)
    return SqliteWorldCatalogue(path)


@pytest.fixture
def synthetic_world_catalogue():
    """Provide the compact world used by domain and service tests."""
    return build_synthetic_world_catalogue()


@pytest.fixture
def synthetic_game(
    database,
    synthetic_vehicle_catalogue,
    synthetic_world_catalogue,
) -> GameService:
    market = build_market_components(
        synthetic_world_catalogue,
        random.Random(7),
        synthetic_vehicle_catalogue,
    )
    service = build_fixture_game(
        database,
        "test-owner",
        synthetic_world_catalogue,
        synthetic_vehicle_catalogue,
        market,
        time.time,
    )
    service.ensure_initial_state()
    seed_test_offers(service)
    return service


@pytest.fixture
def reference_vehicle_catalogue(tmp_path):
    """Copy the packaged vehicle catalogue for repository acceptance."""
    import shutil

    from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue

    path = tmp_path / "catalogue.sqlite3"
    shutil.copyfile(REFERENCE_VEHICLE_PATH, path)
    return SqliteVehicleCatalogue(path)


@pytest.fixture
def synthetic_vehicle_catalogue():
    """Provide compact vehicle models to domain and service tests."""
    return build_synthetic_vehicle_catalogue()


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
def synthetic_runtime(synthetic_game, database):
    return build_test_runtime(synthetic_game, database)
