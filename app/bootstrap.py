"""Dependency assembly for production and test application instances."""

from __future__ import annotations

import random
from pathlib import Path

import httpx

from app.config import Settings
from app.providers.routing import ValhallaTruckRouter
from app.repositories.accounts import AccountRepository
from app.repositories.cached_world_catalogue import CachedWorldCatalogue
from app.repositories.multiplayer_map import MultiplayerMapRepository
from app.repositories.sqlite_store import SqliteStore
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.repositories.world_maintenance import WorldMaintenanceRepository
from app.repositories.world_state_migration import (
    WorldStateMigrationRepository,
)
from app.services.fleet import FleetService
from app.services.game import GameService
from app.services.map_locations import MapLocationService
from app.services.market import MarketGenerator
from app.services.market_scope import MarketScopeResolver
from app.services.multiplayer_map import MultiplayerMapService
from app.services.pricing import PricingService
from app.services.profile_maintenance import ProfileMaintenanceService
from app.services.world_maintenance import WorldMaintenanceService
from app.services.world_state_migration import WorldStateMigrationService
from app.simulation import LEGACY_CARGO_TYPES


def build_game_service(
    settings: Settings,
    routing_client: httpx.AsyncClient,
    rng_seed: int | None = None,
) -> GameService:
    """Assemble the application service graph from explicit dependencies."""
    store = SqliteStore(settings.db_path)
    router = ValhallaTruckRouter(
        store=store,
        client=routing_client,
        base_url=settings.valhalla_url,
        client_id=settings.valhalla_client_id,
    )
    world = build_world_catalogue(settings)
    catalogue = build_vehicle_catalogue(settings)
    market = MarketGenerator(world, random.Random(rng_seed), catalogue)
    pricing = PricingService(LEGACY_CARGO_TYPES)
    return GameService(
        store=store,
        world=world,
        router=router,
        market=market,
        pricing=pricing,
        catalogue=catalogue,
        market_scope=MarketScopeResolver(world),
        time_scale=settings.game_time_scale,
    )


def build_player_service(template: GameService, user_id: str) -> GameService:
    """Isolate game state while sharing rate-limited provider adapters."""
    game = GameService(
        store=SqliteStore(
            template.store.path,
            f"user:{user_id}:",
            initialize_schema=False,
        ),
        world=template.world,
        router=template.router,
        market=template.market,
        pricing=template.pricing,
        catalogue=template.catalogue,
        market_scope=template.market_scope,
        time_scale=template.time_scale,
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
    """Assemble purchasing against the authenticated player's store."""
    return FleetService(
        game.store, build_vehicle_catalogue(settings), game.world
    )


def build_map_service(game: GameService) -> MapLocationService:
    """Project real catalogue locations without a network lookup."""
    return MapLocationService(game.world)


def build_multiplayer_map_service(game: GameService) -> MultiplayerMapService:
    """Build the read-only cross-player traffic projection."""
    return MultiplayerMapService(MultiplayerMapRepository(game.store))


def build_profile_maintenance_service(
    settings: Settings,
) -> ProfileMaintenanceService:
    """Wire local maintenance independently of the HTTP application."""
    accounts = AccountRepository(SqliteStore(settings.db_path))

    def player_store_factory(user_id: str) -> SqliteStore:
        """Resolve the store for a repository-verified account identity."""
        return SqliteStore(settings.db_path, f"user:{user_id}:")

    return ProfileMaintenanceService(
        build_vehicle_catalogue(settings), accounts, player_store_factory
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


def build_world_maintenance_service(path: Path) -> WorldMaintenanceService:
    """Assemble explicit offline maintenance, never from an endpoint."""
    return WorldMaintenanceService(WorldMaintenanceRepository(path))


def build_world_state_migration_service(
    settings: Settings,
) -> WorldStateMigrationService:
    """Assemble the explicit offline profile migration."""
    return WorldStateMigrationService(
        build_world_catalogue(settings),
        WorldStateMigrationRepository(settings.db_path),
    )
