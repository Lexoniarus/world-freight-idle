"""Dependency assembly for production and test application instances."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import Settings
from app.domain.game_import import GameStateImporter
from app.domain.geography_migration import GeographyMigrationStore
from app.domain.ports import TruckRouter, VehicleCatalogue, WorldCatalogue
from app.domain.read_ports import LeaderboardReader, TrafficReader
from app.domain.world_scopes import WorldScope
from app.providers.routing import ValhallaTruckRouter
from app.repositories.accounts import AccountRepository
from app.repositories.cached_world_catalogue import CachedWorldCatalogue
from app.repositories.energy_upgrade import VehicleEnergyUpgradeRepository
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.repositories.leaderboard import SqliteLeaderboardReader
from app.repositories.legacy_game_import import LegacyGameImporter
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.relational_traffic import SqliteTrafficReader
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.repositories.world_geography import WorldGeographyRepository
from app.services.fleet import FleetService
from app.services.game import GameService
from app.services.map_locations import MapLocationService
from app.services.market import MarketGenerator
from app.services.market_scope import MarketScopeResolver
from app.services.profile_maintenance import ProfileMaintenanceService


@dataclass
class GameRuntime:
    """Shared dependencies owned by the application composition root."""

    database: SqliteGameDatabase
    world: WorldCatalogue
    router: TruckRouter
    market: MarketGenerator
    catalogue: VehicleCatalogue
    market_scope: MarketScopeResolver
    time_scale: float
    clock: Callable[[], float] = time.time


def build_game_runtime(
    settings: Settings,
    routing_client: httpx.AsyncClient,
    rng_seed: int | None = None,
) -> GameRuntime:
    """Initialize only relational storage and shared application resources."""
    database = SqliteGameDatabase(settings.db_path)
    database.initialize()
    router = ValhallaTruckRouter(
        cache=SqliteProviderCache(database),
        client=routing_client,
        base_url=settings.valhalla_url,
        client_id=settings.valhalla_client_id,
    )
    world = build_world_catalogue(settings)
    catalogue = build_vehicle_catalogue(settings)
    return GameRuntime(
        database=database,
        world=world,
        router=router,
        market=MarketGenerator(world, random.Random(rng_seed), catalogue),
        catalogue=catalogue,
        market_scope=MarketScopeResolver(world),
        time_scale=settings.game_time_scale,
    )


def build_player_service(runtime: GameRuntime, user_id: str) -> GameService:
    """Bind one authenticated owner to the shared relational transaction."""
    game = GameService(
        unit_of_work=SqliteGameUnitOfWork(runtime.database, user_id),
        world=runtime.world,
        router=runtime.router,
        market=runtime.market,
        catalogue=runtime.catalogue,
        market_scope=runtime.market_scope,
        time_scale=runtime.time_scale,
        clock=runtime.clock,
    )
    game.ensure_initial_state()
    return game


def build_vehicle_catalogue(settings: Settings) -> SqliteVehicleCatalogue:
    """Resolve the bundled catalogue independently of the player database."""
    return SqliteVehicleCatalogue(
        settings.vehicle_catalogue_path
        or settings.base_dir / "data" / "world_freight_vehicle_catalog.sqlite3"
    )


def build_fleet_service(game: GameService, settings: Settings) -> FleetService:
    """Assemble purchasing against the authenticated player's unit of work."""
    return FleetService(
        game.unit_of_work, build_vehicle_catalogue(settings), game.world
    )


def build_map_service(game: GameService) -> MapLocationService:
    """Project real catalogue locations without a network lookup."""
    return MapLocationService(game.world)


def build_traffic_reader(
    runtime: GameRuntime,
) -> TrafficReader:
    """Build the relational cross-player traffic projection."""
    return SqliteTrafficReader(runtime.database)


def build_leaderboard_reader(runtime: GameRuntime) -> LeaderboardReader:
    """Bind the public relational progress reader."""
    return SqliteLeaderboardReader(runtime.database)


def build_profile_maintenance_service(
    settings: Settings,
) -> ProfileMaintenanceService:
    """Wire local maintenance independently of the HTTP application."""
    database = SqliteGameDatabase(settings.db_path)
    database.initialize()
    accounts = AccountRepository(database)

    def player_unit_of_work_factory(user_id: str) -> SqliteGameUnitOfWork:
        """Bind the repository-verified account to its relational state."""
        return SqliteGameUnitOfWork(database, user_id)

    return ProfileMaintenanceService(
        build_vehicle_catalogue(settings),
        accounts,
        player_unit_of_work_factory,
    )


def build_world_catalogue(settings: Settings) -> CachedWorldCatalogue:
    """Resolve one lazily cached immutable runtime world revision."""
    source = SqliteWorldCatalogue(
        settings.world_catalogue_path
        or settings.base_dir
        / "data"
        / "world_freight_company_facility_mvp.sqlite3"
    )
    return CachedWorldCatalogue(source)


def build_geography_migration(
    backup: Path, target: Path
) -> GeographyMigrationStore:
    """Bind offline normalization to its immutable backup and new output."""
    return WorldGeographyRepository(backup, target)


def build_game_importer(
    source: Path, settings: Settings, exclude_global_demo: bool = False
) -> GameStateImporter:
    """Assemble the explicit offline importer without opening runtime state."""
    return LegacyGameImporter(
        source,
        WorldScope(build_world_catalogue(settings).read()),
        MarketGenerator.model_id,
        build_vehicle_catalogue(settings).list_models(),
        exclude_global_demo=exclude_global_demo,
    )


def build_energy_upgrade(
    source: Path, settings: Settings
) -> VehicleEnergyUpgradeRepository:
    """Inject catalogue snapshots into the explicit offline state upgrade."""
    return VehicleEnergyUpgradeRepository(
        source, build_vehicle_catalogue(settings).list_models()
    )
