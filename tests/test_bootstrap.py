import random
from pathlib import Path

import httpx

from app.bootstrap import build_game_runtime, build_market_generation_services
from app.config import Settings
from app.providers.routing import ValhallaTruckRouter
from app.services.routing.anchors import RoutingAnchorResolver
from tests.support.game_service import (
    FixturePlayerGameFacade,
    build_fixture_game,
)


def test_build_game_runtime_wires_real_provider_adapters(tmp_path: Path):
    settings = Settings(
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "game.db",
        nominatim_url="https://n.test",
        valhalla_url="https://v.test",
        http_user_agent="agent",
        valhalla_client_id="client",
        request_timeout_seconds=2,
        game_time_scale=1,
        log_level="INFO",
    )
    routing_client = httpx.AsyncClient()
    runtime = build_game_runtime(
        settings,
        routing_client,
        rng_seed=1,
    )
    assert isinstance(runtime.routing_preparation.router, ValhallaTruckRouter)
    assert isinstance(
        runtime.routing_preparation.anchors, RoutingAnchorResolver
    )
    assert runtime.routing_preparation.router.base_url == "https://v.test"
    assert runtime.database.path == settings.db_path
    import asyncio

    asyncio.run(routing_client.aclose())


def test_player_context_factory_reuses_boundaries_without_state_changes(
    database,
    synthetic_world_catalogue,
    synthetic_vehicle_catalogue,
):
    """Compose production workflows without silently initializing state."""
    market = build_market_generation_services(
        synthetic_world_catalogue,
        random.Random(1),
        synthetic_vehicle_catalogue,
    )
    context = build_fixture_game(
        database,
        "factory-owner",
        synthetic_world_catalogue,
        synthetic_vehicle_catalogue,
        market,
        lambda: 1,
    )
    service = context.service
    assert isinstance(service, FixturePlayerGameFacade)
    assert service.state_repository.get_player() is None
    assert service.initialization.world is synthetic_world_catalogue
    assert service.initialization.catalogue is synthetic_vehicle_catalogue
    assert service.market_lifecycle.generation is market
    assert (
        service.transport_dispatch.market_demand
        is service.player_market.demand
    )
