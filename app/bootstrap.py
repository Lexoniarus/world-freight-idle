"""Dependency assembly for production and test application instances."""

from __future__ import annotations

import random

import httpx

from app.config import Settings
from app.providers.geocoding import NominatimGeocoder
from app.providers.routing import ValhallaTruckRouter
from app.repositories.accounts import AccountRepository
from app.repositories.sqlite_store import SqliteStore
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.seed_data import (
    CARGO_TYPES,
    FICTIONAL_CONSIGNEES,
    FICTIONAL_SHIPPERS,
    HUB_BY_ID,
    HUBS,
)
from app.services.fleet import FleetService
from app.services.game import GameService
from app.services.map_locations import MapLocationService
from app.services.market import MarketGenerator
from app.services.pricing import PricingService
from app.services.profile_maintenance import ProfileMaintenanceService


def build_game_service(
    settings: Settings,
    geocoding_client: httpx.AsyncClient,
    routing_client: httpx.AsyncClient,
    rng_seed: int | None = None,
) -> GameService:
    """Assemble the application service graph from explicit dependencies."""
    store = SqliteStore(settings.db_path)
    geocoder = NominatimGeocoder(
        store=store,
        client=geocoding_client,
        base_url=settings.nominatim_url,
        user_agent=settings.http_user_agent,
    )
    router = ValhallaTruckRouter(
        store=store,
        client=routing_client,
        base_url=settings.valhalla_url,
        client_id=settings.valhalla_client_id,
    )
    market = MarketGenerator(
        hubs=HUBS,
        cargo_types=CARGO_TYPES,
        shipper_names=FICTIONAL_SHIPPERS,
        consignee_names=FICTIONAL_CONSIGNEES,
        rng=random.Random(rng_seed),
    )
    pricing = PricingService(CARGO_TYPES)
    return GameService(
        store=store,
        geocoder=geocoder,
        router=router,
        market=market,
        pricing=pricing,
        hubs_by_id=HUB_BY_ID,
        hubs=HUBS,
        catalogue=build_vehicle_catalogue(settings),
        time_scale=settings.game_time_scale,
    )


def build_player_service(template: GameService, user_id: str) -> GameService:
    """Isolate game state while sharing rate-limited provider adapters."""
    game = GameService(
        store=SqliteStore(template.store.path, f"user:{user_id}:"),
        geocoder=template.geocoder,
        router=template.router,
        market=template.market,
        pricing=template.pricing,
        hubs_by_id=template.hubs_by_id,
        hubs=template.hubs,
        catalogue=template.catalogue,
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
    return FleetService(game.store, build_vehicle_catalogue(settings))


def build_map_service(game: GameService) -> MapLocationService:
    """Reuse the configured geocoder, cache and limiter for public hubs."""
    return MapLocationService(game.geocoder, game.hubs)


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
