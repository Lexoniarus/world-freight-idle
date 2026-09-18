from pathlib import Path

import httpx

from app.bootstrap import build_game_service
from app.config import Settings


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
    geocoding_client = httpx.AsyncClient()
    routing_client = httpx.AsyncClient()
    game = build_game_service(
        settings,
        geocoding_client,
        routing_client,
        rng_seed=1,
    )
    assert game.geocoder.base_url == "https://n.test"
    assert game.router.base_url == "https://v.test"
    assert game.store.path == settings.db_path
    import asyncio

    asyncio.run(geocoding_client.aclose())
    asyncio.run(routing_client.aclose())
