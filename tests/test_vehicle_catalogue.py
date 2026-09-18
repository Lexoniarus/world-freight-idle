"""Catalogue integrity, purchase snapshots and vehicle-specific economics."""

import hashlib
import math
import sqlite3
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import build_fleet_service, build_player_service
from app.domain.errors import CatalogueError
from app.main import create_app
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.services.fleet import FleetService
from tests.conftest import FakeGeocoder, FakeRouter
from tests.test_api import make_settings, make_static_files
from tests.test_game import first_berlin_contract


def test_catalogue_projects_all_offers_without_writing(catalogue):
    before = hashlib.sha256(catalogue.path.read_bytes()).digest()
    models = catalogue.list_models()
    assert len(models) == 8
    assert [(m.price_eur, m.id) for m in models] == sorted(
        (m.price_eur, m.id) for m in models
    )
    first = models[0]
    assert first.id == "iveco_sway_500"
    assert first.price_eur == 149000
    assert first.capacity_tons == 24.2
    assert first.name.startswith("Iveco") or first.name.startswith("IVECO")
    assert first.to_dict()["operating_cost_eur_per_km"] >= 0
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
    fleet = FleetService(game.store, catalogue)
    with pytest.raises(ValueError, match="Reputation"):
        fleet.purchase("daf_xg_plus_480")
    player = game.store.get_json("player")
    player.update(cash=500000, reputation=25)
    game.store.set_json("player", player)
    vehicle = fleet.purchase("daf_xg_plus_480")
    rate = vehicle["operating_cost_eur_per_km"]
    assert vehicle["capacity_tons"] == 24.3
    assert game.store.get_json("player")["cash"] == 338000
    with sqlite3.connect(catalogue.path) as connection:
        connection.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=9"
        )
    assert game.get_vehicle(vehicle["id"])["operating_cost_eur_per_km"] == rate
    before = game.store.get_json("player")
    vehicles = game.store.get_json("vehicles")
    original = game.store.set_json

    def fail_vehicle_write(key, value):
        if key == "vehicles":
            raise RuntimeError("persistence failed")
        original(key, value)

    with patch.object(game.store, "set_json", side_effect=fail_vehicle_write):
        with pytest.raises(RuntimeError):
            fleet.purchase("iveco_sway_500")
    assert game.store.get_json("player") == before
    assert game.store.get_json("vehicles") == vehicles


async def test_vehicle_quotes_and_legacy_snapshots_remain_compatible(
    game, catalogue
):
    legacy = game.store.get_json("vehicles")
    legacy[0].pop("operating_cost_eur_per_km")
    legacy[0].pop("model_id")
    game.store.set_json("vehicles", legacy)
    contract = first_berlin_contract(game)
    first = await game.quote_contract(contract["id"], "truck_01")
    assert first["operating_cost_eur_per_km"] == 0.62
    assert first["vehicle_id"] == "truck_01"
    assert (await game.quote_contract(contract["id"]))["vehicle_id"] is None
    vehicle = FleetService(game.store, catalogue).purchase("iveco_sway_500")
    quote = await game.quote_contract(contract["id"], vehicle["id"])
    assert quote["operating_cost_eur"] == round(
        80 + 400 * vehicle["operating_cost_eur_per_km"]
    )
    assert quote["payout_eur"] == first["payout_eur"]
    assert quote["operating_cost_eur"] != first["operating_cost_eur"]
    before = game.store.get_json("player")["cash"]
    trip = await game.dispatch(contract["id"], vehicle["id"])
    assert trip["operating_cost_eur"] == quote["operating_cost_eur"]
    assert (
        game.store.get_json("player")["cash"]
        == before - quote["operating_cost_eur"]
    )
    # Old balances and models are not migrated by reinitialization.
    game.store.set_json(
        "player", {"cash": 25000, "reputation": 0, "completed": 0}
    )
    legacy = game.store.get_json("vehicles")[0]
    for model_id in (None, "rigid_12t", "semi_24t"):
        game.store.set_json("vehicles", [{**legacy, "model_id": model_id}])
        game.ensure_initial_state()
        assert game.store.get_json("player")["cash"] == 25000
        assert game.get_vehicle("truck_01")["model_id"] == model_id
    # Already running transport economics are independent of the catalogue.
    trip["arrives_at"] = 0
    game.store.set_json("vehicles", [vehicle])
    game.store.set_json("active_trips", [trip])
    assert game.reconcile_arrival()
    assert game.store.get_json("player")["cash"] == 25000 + trip["payout_eur"]


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
        app.state.game.geocoder = FakeGeocoder()
        app.state.game.router = FakeRouter()
        contract = next(
            item
            for item in client.get("/api/v1/contracts").json()["contracts"]
            if item["origin_hub_id"] == "berlin_westhafen"
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
        assert client.post(url).json()["vehicle_id"] is None
        assert len(client.get("/api/v1/fleet/catalogue").json()["models"]) == 8
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


def test_catalogue_builder_default_path(game, catalogue):
    settings = replace(
        make_settings(catalogue.path.parent),
        vehicle_catalogue_path=None,
        base_dir=Path(__file__).resolve().parents[1],
    )
    fleet = build_fleet_service(game, settings)
    assert len(fleet.list_catalogue()["models"]) == 8
    isolated = build_player_service(game, "new-account")
    assert isolated.state()["player"]["cash"] == 175000


def test_packaged_catalogue_works_outside_project_directory(
    tmp_path, monkeypatch
):
    import shutil

    make_static_files(tmp_path)
    settings = make_settings(tmp_path)
    bundled = tmp_path / "data" / "world_freight_vehicle_catalog.sqlite3"
    bundled.parent.mkdir()
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
        assert len(response.json()["models"]) == 8
        assert client.get("/login").status_code == 200


def test_starter_uses_catalogue_snapshot_and_preserves_existing_accounts(
    game, catalogue
):
    model = catalogue.list_models()[0]
    starter = game.get_vehicle("truck_01")
    assert starter["model_id"] == model.id
    assert starter["name"] == model.name
    assert starter["capacity_tons"] == model.capacity_tons
    assert (
        starter["operating_cost_eur_per_km"] == model.operating_cost_eur_per_km
    )
    assert game.store.get_json("player")["cash"] == 175000
    before = game.store.get_json("vehicles")
    with sqlite3.connect(catalogue.path) as db:
        db.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=7"
        )
    game.ensure_initial_state()
    assert game.store.get_json("vehicles") == before
    fresh = build_player_service(game, "fresh")
    assert fresh.get_vehicle("truck_01")["operating_cost_eur_per_km"] == 7
    with patch.object(game.catalogue, "list_models", return_value=()):
        with pytest.raises(CatalogueError, match="Startfahrzeug"):
            build_player_service(game, "failed")
    from app.repositories.sqlite_store import SqliteStore

    failed = SqliteStore(game.store.path, "user:failed:")
    assert failed.get_json("player") is None
    assert failed.get_json("vehicles") is None


def test_missing_catalogue_keeps_login_available_and_new_state_retryable(
    tmp_path,
):
    make_static_files(tmp_path)
    settings = replace(
        make_settings(tmp_path), vehicle_catalogue_path=tmp_path / "missing.db"
    )
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
        assert client.get("/api/v1/fleet").status_code == 503
        import shutil

        shutil.copyfile(
            make_settings(tmp_path).vehicle_catalogue_path,
            settings.vehicle_catalogue_path,
        )
        response = client.get("/api/v1/fleet")
        assert response.status_code == 200
        vehicle = response.json()["vehicles"][0]
        assert vehicle["model_id"] == "iveco_sway_500"
        assert vehicle["image"]["url"]
        assert (
            client.get("/api/v1/dashboard").json()["player"]["cash"] == 175000
        )
