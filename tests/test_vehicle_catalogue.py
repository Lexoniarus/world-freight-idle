"""Catalogue integrity, purchase snapshots and vehicle-specific economics."""

import hashlib
import math
import sqlite3
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.game_projection import (
    project_catalogue,
    project_player,
    project_quote,
    project_state,
    project_transport,
    project_vehicle,
)
from app.bootstrap import build_fleet_service, build_player_service
from app.domain.energy import EnergyProfile
from app.domain.errors import CatalogueError
from app.domain.game import OwnedVehicle, PlayerState
from app.main import create_app
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.services.fleet import FleetService
from tests.conftest import BERLIN_UID, FakeRouter
from tests.test_api import make_settings, make_static_files
from tests.test_game import first_berlin_contract


def test_catalogue_projects_all_offers_without_writing(catalogue):
    before = hashlib.sha256(catalogue.path.read_bytes()).digest()
    models = catalogue.list_models()
    assert len(models) >= 8
    assert [(m.price_eur, m.id) for m in models] == sorted(
        (m.price_eur, m.id) for m in models
    )
    first = next(model for model in models if model.id == "iveco_sway_500")
    assert first.id == "iveco_sway_500"
    assert first.price_eur == 149000
    assert first.capacity_tons == 24.2
    assert first.name.startswith("Iveco") or first.name.startswith("IVECO")
    assert first.operating_cost_eur_per_km >= 0
    assert hashlib.sha256(catalogue.path.read_bytes()).digest() == before
    # File remains replaceable after read: the repository owns no open handle.
    renamed = catalogue.path.with_suffix(".moved")
    catalogue.path.rename(renamed)
    renamed.rename(catalogue.path)


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "corrupt",
        "schema",
        "version",
        "references",
        "empty",
        "incomplete",
        "text",
        "integer",
        "number",
        "range",
    ],
)
def test_catalogue_failures_are_explicit(catalogue, failure):
    if failure == "missing":
        catalogue = SqliteVehicleCatalogue(
            catalogue.path.parent / "missing.db"
        )
    elif failure == "corrupt":
        catalogue.path.write_bytes(b"not sqlite")
    else:
        with sqlite3.connect(catalogue.path) as connection:
            connection.execute("PRAGMA ignore_check_constraints=ON")
            sql = {
                "schema": "DROP TABLE vehicle_balance",
                "version": "UPDATE catalog_metadata SET value='0' WHERE key='schema_version'",
                "references": "UPDATE vehicle_models SET manufacturer_id='missing'",
                "empty": "DELETE FROM vehicle_sources",
                "incomplete": "DELETE FROM vehicle_balance",
                "text": "UPDATE manufacturers SET name='' WHERE manufacturer_id='daf'",
                "integer": "UPDATE vehicle_balance SET purchase_price_eur_game=1.5",
                "number": "UPDATE vehicle_balance SET operating_cost_eur_per_km_game='oops'",
                "range": "UPDATE vehicle_balance SET payload_t_game=-1",
            }[failure]
            connection.execute(sql)
            if failure == "empty":
                for table in (
                    "vehicle_transport_capabilities",
                    "vehicle_images",
                    "vehicle_balance",
                    "vehicle_models",
                ):
                    connection.execute(f"DELETE FROM {table}")
    with pytest.raises(CatalogueError, match="nicht verfügbar"):
        catalogue.list_models()


def test_catalogue_numeric_nonfinite_and_negative_cost(catalogue):
    with sqlite3.connect(catalogue.path) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=?",
            (math.inf,),
        )
    with pytest.raises(CatalogueError):
        catalogue.list_models()
    with sqlite3.connect(catalogue.path) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=-1"
        )
    with pytest.raises(CatalogueError):
        catalogue.list_models()


def test_purchase_reputation_snapshots_and_rollback(game, catalogue):
    fleet = FleetService(game.unit_of_work, catalogue, game.world)
    with pytest.raises(ValueError, match="Reputation"):
        project_vehicle(fleet.purchase("daf_xg_plus_480"))
    player = project_player(game._get_player())
    player.update(cash=500000, reputation=25)
    game.state_repository.save_player(PlayerState(**player))
    vehicle = project_vehicle(fleet.purchase("daf_xg_plus_480"))
    rate = vehicle["operating_cost_eur_per_km"]
    assert vehicle["capacity_tons"] == 24.3
    assert game._get_player().cash == 338000
    with sqlite3.connect(catalogue.path) as connection:
        connection.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=9"
        )
    assert (
        project_vehicle(game.get_vehicle(vehicle["id"]))[
            "operating_cost_eur_per_km"
        ]
        == rate
    )
    before = project_player(game._get_player())
    vehicles = [
        project_vehicle(item) for item in game.state_repository.list_vehicles()
    ]
    with patch.object(
        game.state_repository,
        "save_vehicle",
        side_effect=RuntimeError("persistence failed"),
    ):
        with pytest.raises(RuntimeError):
            project_vehicle(fleet.purchase("iveco_sway_500"))
    assert project_player(game._get_player()) == before
    assert [
        project_vehicle(item) for item in game.state_repository.list_vehicles()
    ] == vehicles


async def test_vehicle_quotes_and_legacy_snapshots_remain_compatible(
    monkeypatch, game, catalogue
):
    original = game.state_repository.list_vehicles()[0]
    legacy = OwnedVehicle(
        original.id,
        original.name,
        original.mode,
        original.capacity_tons,
        original.facility_uid,
        original.status,
        location=original.location,
        energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
        energy_level=100,
        top_speed_kmh=90,
    )
    contract = first_berlin_contract(game)
    game.state_repository.save_vehicle(legacy)
    with pytest.raises(ValueError, match="Bestand"):
        await game.quote_contract(contract["id"], "truck_01")
    game.state_repository.save_vehicle(original)
    original._operating_cost_eur_per_km = 0.5
    game.state_repository.save_vehicle(original)
    first = project_quote(
        await game.quote_contract(contract["id"], "truck_01")
    )
    assert first["maintenance_eur_per_km"] == 0.078
    assert first["vehicle_id"] == "truck_01"
    vehicle = project_vehicle(
        FleetService(game.unit_of_work, catalogue, game.world).purchase(
            "iveco_sway_500"
        )
    )
    quote = project_quote(
        await game.quote_contract(contract["id"], vehicle["id"])
    )
    assert quote["operating_cost_eur"] == round(
        80 + quote["distance_km"] * quote["maintenance_eur_per_km"]
    )
    assert quote["payout_eur"] == first["payout_eur"]
    assert quote["operating_cost_eur"] == first["operating_cost_eur"]
    before = game._get_player().cash
    trip = project_transport(
        await game.dispatch(contract["id"], vehicle["id"])
    )
    assert trip["operating_cost_eur"] == quote["operating_cost_eur"]
    assert game._get_player().cash == before - quote["operating_cost_eur"]
    # Old balances and models are not migrated by reinitialization.
    game.state_repository.save_player(
        PlayerState(cash=25000, reputation=0, completed=0)
    )
    for model_id in (None, "rigid_12t", "semi_24t"):
        legacy = OwnedVehicle(
            original.id,
            original.name,
            original.mode,
            original.capacity_tons,
            original.facility_uid,
            "idle",
            model_id=model_id,
            location=original.location,
            energy=EnergyProfile("diesel", "l", 100, 20, 10, 0.1),
            energy_level=100,
            top_speed_kmh=90,
        )
        game.state_repository.save_vehicle(legacy)
        game.ensure_initial_state()
        assert game._get_player().cash == 25000
        assert (
            project_vehicle(game.get_vehicle("truck_01"))["model_id"]
            == model_id
        )
    # Already running transport economics are independent of the catalogue.
    monkeypatch.setattr(game, "now", lambda: trip["arrives_at"] + 1)
    assert game.get_vehicle(vehicle["id"]).status == "enroute"
    assert game.reconcile_arrival()
    assert game._get_player().cash == 25000 + trip["payout_eur"]


def test_catalogue_api_errors_and_vehicle_quote_validation(tmp_path):
    make_static_files(tmp_path)
    settings = make_settings(tmp_path)
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
        app.state.game.router = FakeRouter()
        contract = next(
            item
            for item in client.get("/api/v1/contracts").json()["contracts"]
            if item["origin_hub_id"] == BERLIN_UID
        )
        url = f"/api/v1/contracts/{contract['id']}/quote"
        assert (
            client.post(url, json={"vehicle_id": "foreign"}).status_code == 400
        )
        assert (
            client.post(url, json={"vehicle_id": "truck_01"}).json()[
                "vehicle_id"
            ]
            == "truck_01"
        )
        assert client.post(url).status_code == 422
        assert len(client.get("/api/v1/fleet/catalogue").json()["models"]) >= 8
        app.state.settings = replace(
            settings, vehicle_catalogue_path=tmp_path / "missing.db"
        )
        assert client.get("/api/v1/fleet/catalogue").status_code == 503
        assert (
            client.post(
                "/api/v1/fleet/purchase", json={"model_id": "iveco_sway_500"}
            ).status_code
            == 503
        )
        assert client.get("/api/v1/fleet").status_code == 200
        assert (
            client.get("/api/v1/dashboard").json()["player"]["cash"] == 175000
        )


def test_catalogue_builder_default_path(runtime, game, catalogue):
    with runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("new-account", "new-account", "test-only"),
        )
    settings = replace(
        make_settings(catalogue.path.parent),
        vehicle_catalogue_path=None,
        base_dir=Path(__file__).resolve().parents[1],
    )
    fleet = build_fleet_service(game, settings)
    assert len(project_catalogue(fleet.list_catalogue())["models"]) >= 8
    isolated = build_player_service(runtime, "new-account")
    assert project_state(isolated.state())["player"]["cash"] == 175000


def test_packaged_catalogue_works_outside_project_directory(
    tmp_path, monkeypatch
):
    import shutil

    make_static_files(tmp_path)
    settings = make_settings(tmp_path)
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


def test_starter_uses_catalogue_snapshot_and_preserves_existing_accounts(
    database, runtime, game, catalogue
):
    with runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("failed", "failed", "test-only"),
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("fresh", "fresh", "test-only"),
        )
    model = next(
        item for item in catalogue.list_models() if item.id == "iveco_sway_500"
    )
    starter = project_vehicle(game.get_vehicle("truck_01"))
    assert starter["model_id"] == model.id
    assert starter["name"] == model.name
    assert starter["capacity_tons"] == model.capacity_tons
    assert (
        starter["operating_cost_eur_per_km"] == model.operating_cost_eur_per_km
    )
    assert game._get_player().cash == 175000
    before = [
        project_vehicle(item) for item in game.state_repository.list_vehicles()
    ]
    with sqlite3.connect(catalogue.path) as db:
        db.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=7"
        )
    game.ensure_initial_state()
    assert [
        project_vehicle(item) for item in game.state_repository.list_vehicles()
    ] == before
    fresh = build_player_service(runtime, "fresh")
    assert (
        project_vehicle(fresh.get_vehicle("truck_01"))[
            "operating_cost_eur_per_km"
        ]
        == 7
    )
    with patch.object(game.catalogue, "list_models", return_value=()):
        with pytest.raises(CatalogueError, match="Startfahrzeug"):
            build_player_service(runtime, "failed")
    from app.repositories.game_state import SqliteGameStateRepository

    failed = SqliteGameStateRepository(database, "failed")
    assert failed.get_player() is None
    assert failed.list_vehicles() == ()


def test_missing_catalogue_blocks_start_and_repaired_start_is_retryable(
    tmp_path,
):
    make_static_files(tmp_path)
    settings = replace(
        make_settings(tmp_path), vehicle_catalogue_path=tmp_path / "missing.db"
    )
    with pytest.raises(CatalogueError):
        with TestClient(create_app(settings)):
            pytest.fail("Server must not become ready with missing catalogue")
    source = make_settings(tmp_path).vehicle_catalogue_path
    assert source is not None and settings.vehicle_catalogue_path is not None
    import shutil

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
        import shutil

        source = make_settings(tmp_path).vehicle_catalogue_path
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


@pytest.mark.parametrize("value", [-1, math.inf, "invalid"])
def test_catalogue_rejects_invalid_explicit_maintenance(catalogue, value):
    with sqlite3.connect(catalogue.path) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE vehicle_balance SET maintenance_eur_per_1000_km_game=?",
            (value,),
        )
    with pytest.raises(CatalogueError):
        catalogue.list_models()


def test_catalogue_requires_explicit_maintenance_column(catalogue):
    with sqlite3.connect(catalogue.path) as connection:
        connection.execute(
            "ALTER TABLE vehicle_balance RENAME COLUMN "
            "maintenance_eur_per_1000_km_game TO unavailable_maintenance"
        )
    with pytest.raises(CatalogueError):
        catalogue.list_models()
