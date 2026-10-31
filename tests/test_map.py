"""Stored coordinates are the only runtime map location source."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_game_service
from app.domain.errors import WorldCatalogueError
from app.domain.world import FacilityQuery
from app.main import create_app
from app.services.map_locations import MapLocationService
from tests.support.api import make_settings, make_static_files


@pytest.mark.asyncio
async def test_map_hubs_resolve_and_preserve_read_failures(synthetic_game):
    service = MapLocationService(synthetic_game.world)
    result = service.list_facilities(FacilityQuery()).facilities
    assert len(result) == 6
    assert all(hub.resolution_status == "resolved" for hub in result)
    berlin = next(h for h in result if "berlin_westhafen" in h.aliases)
    assert berlin.coordinates is not None
    assert berlin.coordinates.latitude == 52.536
    projection = service.list_facilities(FacilityQuery.parse("13,52,14,53"))
    assert berlin in projection.facilities
    assert projection.unavailable_count == 0
    with patch.object(
        synthetic_game.world,
        "read",
        side_effect=WorldCatalogueError("unavailable"),
    ):
        with pytest.raises(WorldCatalogueError):
            service.list_facilities(FacilityQuery()).facilities


def test_map_endpoint_requires_session_and_uses_game_provider(
    tmp_path, synthetic_game
):
    make_static_files(tmp_path)
    application = create_app(make_settings(tmp_path))
    with TestClient(application) as client:
        for route in ("hubs", "facilities"):
            assert client.get(f"/api/v1/map/{route}").status_code == 401
        application.dependency_overrides[get_game_service] = lambda: (
            synthetic_game
        )
        response = client.get("/api/v1/map/hubs")
        assert response.status_code == 200
        assert len(response.json()["hubs"]) == 6
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
        with patch.object(
            synthetic_game.world,
            "read",
            side_effect=WorldCatalogueError("unavailable"),
        ):
            assert client.get("/api/v1/map/facilities").status_code == 503
