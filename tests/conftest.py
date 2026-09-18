from __future__ import annotations

import random
from pathlib import Path

import pytest

from app.domain.models import RouteResult
from app.repositories.sqlite_store import SqliteStore
from app.seed_data import (
    CARGO_TYPES,
    FICTIONAL_CONSIGNEES,
    FICTIONAL_SHIPPERS,
    HUB_BY_ID,
    HUBS,
)
from app.services.game import GameService
from app.services.market import MarketGenerator
from app.services.pricing import PricingService


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


@pytest.fixture
def game(store: SqliteStore, catalogue) -> GameService:
    market = MarketGenerator(
        hubs=HUBS,
        cargo_types=CARGO_TYPES,
        shipper_names=FICTIONAL_SHIPPERS,
        consignee_names=FICTIONAL_CONSIGNEES,
        rng=random.Random(7),
    )
    service = GameService(
        store=store,
        geocoder=FakeGeocoder(),
        router=FakeRouter(),
        market=market,
        pricing=PricingService(CARGO_TYPES),
        hubs_by_id=HUB_BY_ID,
        hubs=HUBS,
        catalogue=catalogue,
        time_scale=1.0,
    )
    with store.transaction():
        service.ensure_initial_state()
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
