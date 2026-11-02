"""Public HTTP errors conceal private persistence and catalogue details."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_game_service
from app.domain.errors import (
    CatalogueError,
    PersistenceError,
    UnresolvedVehicleModel,
)
from app.main import create_app
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)


def test_persistence_outage_does_not_expose_database_details(tmp_path):
    (tmp_path / "static").mkdir()
    application = create_app(build_synthetic_application_settings(tmp_path))

    def unavailable():
        raise PersistenceError("private database path and contents")

    application.dependency_overrides[get_game_service] = unavailable
    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/dashboard")
    assert response.status_code == 503
    assert response.json() == {"detail": "Spielstand derzeit nicht verfügbar."}
    assert "private" not in response.text
    assert response.headers["x-trace-id"]


def test_market_reference_errors_have_explicit_http_responses(
    tmp_path,
    synthetic_game,
):
    create_minimal_static_files(tmp_path)
    application = create_app(build_synthetic_application_settings(tmp_path))
    application.dependency_overrides[get_game_service] = lambda: synthetic_game
    with TestClient(application) as client:
        for error, status, message in (
            (CatalogueError("private path"), 503, "Fahrzeugkatalog"),
            (
                UnresolvedVehicleModel("private identity"),
                409,
                "Bestand prüfen",
            ),
        ):
            with patch.object(
                synthetic_game, "read_market", side_effect=error
            ):
                response = client.get("/api/v1/contracts?vehicle_id=truck_01")
            assert response.status_code == status
            assert message in response.json()["detail"]
            assert "private" not in response.text


def test_request_initialization_catalogue_failure_is_explicit(tmp_path):
    create_minimal_static_files(tmp_path)
    application = create_app(build_synthetic_application_settings(tmp_path))
    with TestClient(application) as client:
        client.headers["X-Freight-Request"] = "1"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "OfflineOwner",
                "password": "a-valid-password-123",
            },
        )
        with patch(
            "app.api.v1.dependencies.build_player_service",
            side_effect=CatalogueError("Unavailable catalogue"),
        ):
            assert client.get("/api/v1/dashboard").status_code == 503
