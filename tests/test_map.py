"""Stored coordinates are the only runtime map location source."""

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_game_service
from app.domain.errors import WorldCatalogueError
from app.domain.world import FacilityQuery
from app.main import create_app
from app.services.map_locations import MapLocationService
from tests.test_api import make_settings, make_static_files


@pytest.mark.asyncio
async def test_map_hubs_resolve_and_preserve_partial_failures(game):
    service = MapLocationService(game.world)
    result = service.list_facilities(FacilityQuery()).facilities
    assert len(result) == 559
    assert all(hub.resolution_status == "resolved" for hub in result)
    berlin = next(h for h in result if "berlin_westhafen" in h.aliases)
    assert berlin.coordinates is not None
    assert berlin.coordinates.latitude == 52.5374096
    projection = service.list_facilities(FacilityQuery.parse("13,52,14,53"))
    assert berlin in projection.facilities
    assert projection.unavailable_count == 0
    game.world.path.unlink()
    with pytest.raises(WorldCatalogueError):
        service.list_facilities(FacilityQuery()).facilities


def test_map_endpoint_requires_session_and_uses_game_provider(tmp_path, game):
    make_static_files(tmp_path)
    application = create_app(make_settings(tmp_path))
    with TestClient(application) as client:
        for route in ("hubs", "facilities"):
            assert client.get(f"/api/v1/map/{route}").status_code == 401
        application.dependency_overrides[get_game_service] = lambda: game
        response = client.get("/api/v1/map/hubs")
        assert response.status_code == 200
        assert len(response.json()["hubs"]) == 559
        assert (
            response.headers["Referrer-Policy"]
            == "strict-origin-when-cross-origin"
        )
        assert client.get("/api/v1/map/facilities?bbox=bad").status_code == 422
        assert (
            client.get("/api/v1/map/facilities?bbox=170,-90,-170,90").json()[
                "facilities"
            ]
            == []
        )
        game.world.path.unlink()
        assert client.get("/api/v1/map/facilities").status_code == 503
