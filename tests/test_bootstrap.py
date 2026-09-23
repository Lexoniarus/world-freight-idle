from pathlib import Path

import httpx

from app.bootstrap import build_game_runtime
from app.config import Settings
from app.providers.routing import ValhallaTruckRouter


def test_build_game_service_wires_real_provider_adapters(tmp_path: Path):
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
    game = build_game_runtime(
        settings,
        routing_client,
        rng_seed=1,
    )
    assert isinstance(game.router, ValhallaTruckRouter)
    assert game.router.base_url == "https://v.test"
    assert game.database.path == settings.db_path
    import asyncio

    asyncio.run(routing_client.aclose())
