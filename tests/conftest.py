from __future__ import annotations

import random
from pathlib import Path

import pytest

from app.domain.models import RouteResult
from app.repositories.sqlite_store import SqliteStore
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.services.game import GameService
from app.services.market import MarketGenerator
from app.services.market_scope import MarketScopeResolver
from app.services.pricing import PricingService
from tests.seed_data import (
    CARGO_TYPES,
    HUBS,
)


class FakeGeocoder:
    async def geocode(self, address: str) -> tuple[float, float, str]:
        coordinates = {
            HUBS[0].address: (52.5367, 13.3407),
            HUBS[1].address: (53.5083, 9.9286),
            HUBS[2].address: (51.4280, 6.7370),
            HUBS[3].address: (51.9508, 4.0407),
        }
        lat, lon = coordinates[address]
        return lat, lon, address


class FakeRouter:
    async def route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteResult:
        return RouteResult(
            distance_km=400.0,
            duration_seconds=14400.0,
            route_geojson={
                "type": "LineString",
                "coordinates": [
                    [origin_lon, origin_lat],
                    [destination_lon, destination_lat],
                ],
            },
            provider="fake-router",
        )


@pytest.fixture
def store(tmp_path: Path) -> SqliteStore:
    return SqliteStore(tmp_path / "game.db")


WORLD_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "world_freight_company_facility_mvp.sqlite3"
)
BERLIN_UID = (
    SqliteWorldCatalogue(WORLD_PATH)
    .read()
    .get_facility("berlin_westhafen")
    .facility_uid
)


@pytest.fixture
def world_catalogue(tmp_path):
    import shutil

    path = tmp_path / "world.sqlite3"
    shutil.copyfile(WORLD_PATH, path)
    return SqliteWorldCatalogue(path)


@pytest.fixture
def game(store: SqliteStore, catalogue, world_catalogue) -> GameService:
    market = MarketGenerator(world_catalogue, random.Random(7), catalogue)
    service = GameService(
        store=store,
        world=world_catalogue,
        router=FakeRouter(),
        market=market,
        market_scope=MarketScopeResolver(world_catalogue),
        pricing=PricingService(CARGO_TYPES),
        catalogue=catalogue,
        time_scale=1.0,
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
