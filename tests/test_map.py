"""Map projections preserve real coordinates and tolerate provider outages."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_game_service
from app.main import create_app
from app.providers.geocoding import GeocodingError
from app.services.map_locations import MapLocationService
from tests.test_api import make_settings, make_static_files


@pytest.mark.asyncio
async def test_map_hubs_resolve_and_preserve_partial_failures(game):
    service = MapLocationService(game.geocoder, game.hubs)
    result = await service.list_hubs()
    assert len(result) == 4
    assert result[0]["lat"] == 52.5367
    assert all(hub["resolution_status"] == "resolved" for hub in result)
    assert result[0]["address"] == game.hubs[0].address

    service.geocoder = AsyncMock()
    service.geocoder.geocode.side_effect = [
        GeocodingError("not found"),
        GeocodingError("offline"),
        ValueError("invalid coordinate"),
        KeyError("malformed response"),
    ]
    failures = await service.list_hubs()
    assert all(hub["resolution_status"] == "unavailable" for hub in failures)
    assert all(hub["lat"] is None and hub["lon"] is None for hub in failures)
    assert [hub["id"] for hub in failures] == [hub.id for hub in game.hubs]
    service.geocoder.geocode.side_effect = [
        (float("nan"), 0, "invalid"),
        (0, float("inf"), "invalid"),
        (91, 0, "invalid"),
        (0, 181, "invalid"),
    ]
    invalid = await service.list_hubs()
    assert all(hub["resolution_status"] == "unavailable" for hub in invalid)


def test_map_endpoint_requires_session_and_uses_game_provider(tmp_path, game):
    make_static_files(tmp_path)
    application = create_app(make_settings(tmp_path))
    with TestClient(application) as client:
        assert client.get("/api/v1/map/hubs").status_code == 401
        application.dependency_overrides[get_game_service] = lambda: game
        response = client.get("/api/v1/map/hubs")
        assert response.status_code == 200
        assert len(response.json()["hubs"]) == 4
        assert response.json()["hubs"][0]["resolution_status"] == "resolved"
        assert (
            response.headers["Referrer-Policy"]
            == "strict-origin-when-cross-origin"
        )
