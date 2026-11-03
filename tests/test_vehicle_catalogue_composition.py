"""Vehicle-catalogue composition and startup failure boundaries."""

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1.game_projection import project_catalogue, project_vehicle
from app.bootstrap import (
    build_fleet_service,
    build_player_context,
    build_player_service,
    build_vehicle_catalogue,
)
from app.domain.errors import CatalogueError
from app.main import create_app
from app.repositories.game_state import SqliteGameStateRepository
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)
from tests.support.catalogues import InMemoryVehicleCatalogue


def test_fleet_builder_reuses_validated_runtime_catalogue(
    synthetic_runtime,
    synthetic_game,
):
    with synthetic_runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("new-account", "new-account", "test-only"),
        )
    fleet = build_fleet_service(
        synthetic_runtime,
        build_player_context(synthetic_runtime, "test-owner"),
    )
    assert len(project_catalogue(fleet.list_catalogue())["models"]) == len(
        synthetic_runtime.catalogue.list_models()
    )
    isolated = build_player_service(synthetic_runtime, "new-account")
    assert isolated.player_state().cash == 175000


def test_catalogue_builder_default_path(tmp_path):
    settings = replace(
        build_synthetic_application_settings(tmp_path),
        vehicle_catalogue_path=None,
        base_dir=Path(__file__).resolve().parents[1],
    )
    assert len(build_vehicle_catalogue(settings).list_models()) >= 8


def test_starter_uses_catalogue_snapshot_and_preserves_existing_accounts(
    synthetic_game_context,
    database,
    synthetic_runtime,
    synthetic_game,
):
    with synthetic_runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("failed", "failed", "test-only"),
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("fresh", "fresh", "test-only"),
        )
    model = next(
        item
        for item in synthetic_game_context.catalogue.list_models()
        if item.id == "iveco_sway_500"
    )
    starter = project_vehicle(synthetic_game.get_vehicle("truck_01"))
    assert starter["model_id"] == model.id
    assert starter["name"] == model.name
    assert starter["capacity_tons"] == model.capacity_tons
    assert starter["operating_cost_eur_per_km"] == (
        model.operating_cost_eur_per_km
    )
    assert synthetic_game.player_state().cash == 175000
    before = [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ]
    changed = replace(model, operating_cost_eur_per_km=7)
    synthetic_runtime.catalogue = InMemoryVehicleCatalogue(
        tuple(
            changed if item.id == changed.id else item
            for item in synthetic_game_context.catalogue.list_models()
        )
    )
    synthetic_game.ensure_initial_state()
    assert [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ] == before
    fresh = build_player_service(synthetic_runtime, "fresh")
    assert (
        project_vehicle(fresh.get_vehicle("truck_01"))[
            "operating_cost_eur_per_km"
        ]
        == 7
    )
    synthetic_runtime.catalogue = InMemoryVehicleCatalogue(())
    with pytest.raises(CatalogueError, match="Startfahrzeug"):
        build_player_service(synthetic_runtime, "failed")
    failed = SqliteGameStateRepository(database, "failed")
    assert failed.get_player() is None
    assert failed.list_vehicles() == ()


def test_missing_catalogue_blocks_start_and_repaired_start_is_retryable(
    tmp_path,
):
    create_minimal_static_files(tmp_path)
    settings = replace(
        build_synthetic_application_settings(tmp_path),
        vehicle_catalogue_path=tmp_path / "missing.db",
    )
    with pytest.raises(CatalogueError):
        with TestClient(create_app(settings)):
            pytest.fail("Server must not become ready with missing catalogue")
    source = build_synthetic_application_settings(
        tmp_path
    ).vehicle_catalogue_path
    assert source is not None and settings.vehicle_catalogue_path is not None
    shutil.copyfile(source, settings.vehicle_catalogue_path)
    with TestClient(create_app(settings)) as client:
        client.headers["X-Freight-Request"] = "1"
        assert client.get("/login").status_code == 200
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "RetryStarter",
                "password": "test-starter-password",
            },
        ).raise_for_status()
        source = build_synthetic_application_settings(
            tmp_path
        ).vehicle_catalogue_path
        assert source is not None
        assert settings.vehicle_catalogue_path is not None
        shutil.copyfile(source, settings.vehicle_catalogue_path)
        response = client.get("/api/v1/fleet")
        assert response.status_code == 200
        vehicle = response.json()["vehicles"][0]
        assert vehicle["model_id"] == "iveco_sway_500"
        assert vehicle["image"]["url"]
        assert (
            client.get("/api/v1/dashboard").json()["player"]["cash"] == 175000
        )
