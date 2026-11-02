"""Vehicle-catalogue HTTP translation and packaged application access."""

import shutil
from dataclasses import replace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.fleet import get_catalogue, purchase_vehicle
from app.api.v1.schemas import PurchaseRequest
from app.domain.errors import CatalogueError
from app.main import create_app
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
    build_vehicle_reference_application_settings,
)


def test_catalogue_api_uses_validated_startup_snapshot(tmp_path):
    create_minimal_static_files(tmp_path)
    settings = build_synthetic_application_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        client.headers["X-Freight-Request"] = "1"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "Catalogue",
                "password": "catalogue-test-password",
            },
        ).raise_for_status()
        assert len(client.get("/api/v1/fleet/catalogue").json()["models"]) == 4
        app.state.settings = replace(
            settings,
            vehicle_catalogue_path=tmp_path / "missing.db",
        )
        cached = client.get("/api/v1/fleet/catalogue")
        assert cached.status_code == 200
        assert len(cached.json()["models"]) == 4
        assert client.get("/api/v1/fleet").status_code == 200
        assert (
            client.get("/api/v1/dashboard").json()["player"]["cash"] == 175000
        )


def test_fleet_api_translates_catalogue_failures():
    from unittest.mock import MagicMock

    fleet = MagicMock()
    failure = CatalogueError("Catalogue unavailable")
    fleet.list_catalogue.side_effect = failure
    with pytest.raises(HTTPException) as catalogue_error:
        get_catalogue(fleet)
    assert catalogue_error.value.status_code == 503

    fleet.purchase.side_effect = failure
    game = MagicMock()
    with pytest.raises(HTTPException) as purchase_error:
        purchase_vehicle(PurchaseRequest(model_id="model"), fleet, game)
    assert purchase_error.value.status_code == 503
    game.reconcile_arrival.assert_called_once_with()


def test_packaged_catalogue_works_outside_project_directory(
    tmp_path,
    monkeypatch,
):
    create_minimal_static_files(tmp_path)
    settings = build_vehicle_reference_application_settings(tmp_path)
    bundled = tmp_path / "data" / "world_freight_vehicle_catalog.sqlite3"
    bundled.parent.mkdir()
    assert settings.vehicle_catalogue_path is not None
    shutil.copyfile(settings.vehicle_catalogue_path, bundled)
    settings = replace(
        settings,
        vehicle_catalogue_path=None,
        db_path=tmp_path / "players" / "game.db",
    )
    elsewhere = tmp_path / "working-directory"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with TestClient(create_app(settings)) as client:
        client.headers["X-Freight-Request"] = "1"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "Packaged",
                "password": "packaged-test-password",
            },
        ).raise_for_status()
        response = client.get("/api/v1/fleet/catalogue")
        assert response.status_code == 200
        assert len(response.json()["models"]) >= 8
        assert client.get("/login").status_code == 200
