from pathlib import Path

import httpx

from app.bootstrap import build_game_runtime
from app.config import Settings
from app.providers.routing import ValhallaTruckRouter
from app.services.routing.anchors import RoutingAnchorResolver
from tests.support.game_service import FixturePlayerGameFacade


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


def test_player_context_factory_reuses_injected_test_boundaries(
    synthetic_game_context,
):
    """Use the production composition owner with test-only adapters."""
    service = synthetic_game_context.service
    assert isinstance(service, FixturePlayerGameFacade)
    assert service.initialization.world is synthetic_game_context.world
    assert service.initialization.catalogue is synthetic_game_context.catalogue
    assert (
        service.market_lifecycle.generation
        is synthetic_game_context.market_generation
    )
    assert (
        service.transport_dispatch.market_demand
        is service.player_market.demand
    )
