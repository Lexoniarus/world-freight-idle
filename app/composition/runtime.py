"""Shared runtime, catalogue and provider dependency assembly."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

import httpx

from app.config import Settings
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.providers.geocoding import NominatimGeocoder
from app.providers.request_limiter import ProviderRequestLimiter
from app.providers.routing import ValhallaTruckRouter
from app.providers.routing_anchor import ValhallaTruckAnchorLocator
from app.repositories.cached_vehicle_catalogue import CachedVehicleCatalogue
from app.repositories.cached_world_catalogue import CachedWorldCatalogue
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.market_preparation import SqlitePreparationStore
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_readiness import SqliteRoutingReadinessStore
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.services.market.candidates import MarketCandidateService
from app.services.market.contract_factory import ContractFactory
from app.services.market.generation_services import MarketGenerationServices
from app.services.market.scope import MarketScopeResolver
from app.services.market.vehicle_coverage import VehicleCoverageService
from app.services.routing.anchors import RoutingAnchorResolver
from app.services.routing.evidence import RoutingEvidenceReader
from app.services.routing.preparation import RoutingPreparationService


@dataclass
class GameRuntime:
    """Shared dependencies owned by the application composition root."""

    database: SqliteGameDatabase
    world: WorldCatalogue
    market_generation: MarketGenerationServices
    catalogue: VehicleCatalogue
    market_scope: MarketScopeResolver
    routing_evidence: RoutingEvidenceReader
    routing_preparation: RoutingPreparationService
    preparation_jobs: SqlitePreparationStore
    time_scale: float
    clock: Callable[[], float] = time.time


def build_routing_anchor_resolver(
    database: SqliteGameDatabase,
    settings: Settings,
    provider_client: httpx.AsyncClient,
    clock: Callable[[], float],
    limiter: ProviderRequestLimiter | None = None,
    evidence: SqliteRoutingReadinessStore | None = None,
) -> RoutingAnchorResolver:
    """Wire global truck anchors outside immutable world references."""
    cache = SqliteProviderCache(database)
    return RoutingAnchorResolver(
        store=SqliteRoutingAnchorRepository(database),
        locator=ValhallaTruckAnchorLocator(
            provider_client,
            settings.valhalla_url,
            settings.valhalla_client_id,
            limiter,
            partial(evidence.observe_provider_revision, settings.valhalla_url)
            if evidence
            else None,
        ),
        geocoder=NominatimGeocoder(
            cache,
            provider_client,
            settings.nominatim_url,
            settings.http_user_agent,
        ),
        max_snap_distance_m=settings.routing_anchor_max_snap_m,
        clock=clock,
        evidence=evidence,
        provider_revision=partial(
            evidence.provider_revision, settings.valhalla_url
        )
        if evidence
        else None,
    )


def build_game_runtime(
    settings: Settings,
    routing_client: httpx.AsyncClient,
    rng_seed: int | None = None,
    clock: Callable[[], float] = time.time,
) -> GameRuntime:
    """Initialize only relational storage and shared application resources."""
    database = SqliteGameDatabase(settings.db_path)
    database.initialize()
    cache = SqliteProviderCache(database)
    evidence = SqliteRoutingReadinessStore(database)
    jobs = SqlitePreparationStore(database)
    SqliteMarketTemplateStore.initialize(database)
    SqlitePlayerMarketStockStore.initialize(database)
    limiter = ProviderRequestLimiter(
        settings.valhalla_concurrency, settings.valhalla_minimum_interval
    )
    router = ValhallaTruckRouter(
        cache=cache,
        client=routing_client,
        base_url=settings.valhalla_url,
        client_id=settings.valhalla_client_id,
        limiter=limiter,
        cache_enabled=False,
        revision_observer=partial(
            evidence.observe_provider_revision, settings.valhalla_url
        ),
    )
    world = build_world_catalogue(settings)
    catalogue = CachedVehicleCatalogue(build_vehicle_catalogue(settings))
    anchors = build_routing_anchor_resolver(
        database, settings, routing_client, clock, limiter, evidence
    )
    routing_evidence = RoutingEvidenceReader(
        evidence,
        SqliteRoutingAnchorRepository(database),
        world,
        settings.valhalla_url,
        clock,
        anchors.max_snap_distance_m,
        provider_revision=partial(
            evidence.provider_revision, settings.valhalla_url
        ),
    )
    routing_preparation = RoutingPreparationService(
        routing_evidence,
        evidence,
        anchors,
        router,
        world,
        clock,
    )
    return GameRuntime(
        routing_evidence=routing_evidence,
        routing_preparation=routing_preparation,
        preparation_jobs=jobs,
        database=database,
        world=world,
        market_generation=build_market_generation_services(
            world, random.Random(rng_seed), catalogue
        ),
        catalogue=catalogue,
        market_scope=MarketScopeResolver(world),
        time_scale=settings.game_time_scale,
        clock=clock,
    )


def build_vehicle_catalogue(settings: Settings) -> SqliteVehicleCatalogue:
    """Resolve the bundled catalogue independently of the player database."""
    return SqliteVehicleCatalogue(
        settings.vehicle_catalogue_path
        or settings.base_dir / "data" / "world_freight_vehicle_catalog.sqlite3"
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


def build_market_generation_services(
    world: WorldCatalogue,
    rng: random.Random,
    catalogue: VehicleCatalogue,
) -> MarketGenerationServices:
    """Bundle independent candidate, materialization and coverage services."""
    return MarketGenerationServices(
        MarketCandidateService(world, catalogue),
        ContractFactory(rng),
        VehicleCoverageService(),
    )
