"""Catalogue integrity, purchase snapshots and vehicle-specific economics."""

import hashlib
import math
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.fleet import get_catalogue, purchase_vehicle
from app.api.v1.game_projection import (
    project_catalogue,
    project_player,
    project_quote,
    project_state,
    project_transport,
    project_vehicle,
)
from app.api.v1.schemas import PurchaseRequest
from app.bootstrap import (
    build_fleet_service,
    build_player_service,
    build_vehicle_catalogue,
)
from app.domain.energy import EnergyProfile
from app.domain.errors import CatalogueError
from app.domain.game import OwnedVehicle, PlayerState
from app.main import create_app
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.services.gameplay.fleet import FleetService
from tests.support.api import make_settings, make_static_files
from tests.support.catalogues import BERLIN_UID, InMemoryVehicleCatalogue
from tests.support.game import first_berlin_contract
from tests.support.game_clock import set_game_clock
from tests.support.routing_runtime import (
    install_fake_routing_providers,
    prepare_client_market,
)


def test_catalogue_projects_all_offers_without_writing(
    reference_vehicle_catalogue,
):
    before = hashlib.sha256(
        reference_vehicle_catalogue.path.read_bytes()
    ).digest()
    models = reference_vehicle_catalogue.list_models()
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
    assert all(model.energy.capacity > 0 for model in models)
    assert all(model.top_speed_kmh > 0 for model in models)
    assert all(model.transport_capabilities for model in models)
    assert all(model.image is not None for model in models)
    assert first.energy == EnergyProfile("diesel", "l", 1010, 24.5, 10, 0.1)
    electric = next(
        model for model in models if model.id == "mercedes_eactros_600"
    )
    assert electric.energy == EnergyProfile(
        "electric", "kWh", 600, 103, 35, 0.1
    )
    gas = next(model for model in models if model.id == "scania_r460_gas")
    assert gas.energy == EnergyProfile("gas", "kg", 400, 22.2, 25, 0.1)
    assert first.image is not None
    assert first.image.url.startswith("https://upload.wikimedia.org/")
    assert first.image.author
    assert first.image.license_name == "CC0 1.0"
    assert (
        hashlib.sha256(reference_vehicle_catalogue.path.read_bytes()).digest()
        == before
    )
    # File remains replaceable after read: the repository owns no open handle.
    renamed = reference_vehicle_catalogue.path.with_suffix(".moved")
    reference_vehicle_catalogue.path.rename(renamed)
    renamed.rename(reference_vehicle_catalogue.path)


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
def test_catalogue_failures_are_explicit(small_vehicle_catalogue, failure):
    if failure == "missing":
        small_vehicle_catalogue = SqliteVehicleCatalogue(
            small_vehicle_catalogue.path.parent / "missing.db"
        )
    elif failure == "corrupt":
        small_vehicle_catalogue.path.write_bytes(b"not sqlite")
    else:
        with (
            closing(
                sqlite3.connect(small_vehicle_catalogue.path)
            ) as connection,
            connection,
        ):
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
        small_vehicle_catalogue.list_models()


def test_catalogue_numeric_nonfinite_and_negative_cost(
    small_vehicle_catalogue,
):
    with (
        closing(sqlite3.connect(small_vehicle_catalogue.path)) as connection,
        connection,
    ):
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=?",
            (math.inf,),
        )
    with pytest.raises(CatalogueError):
        small_vehicle_catalogue.list_models()
    with (
        closing(sqlite3.connect(small_vehicle_catalogue.path)) as connection,
        connection,
    ):
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=-1"
        )
    with pytest.raises(CatalogueError):
        small_vehicle_catalogue.list_models()


def test_purchase_reputation_snapshots_and_rollback(
    synthetic_game_context, synthetic_game, small_vehicle_catalogue
):
    fleet = FleetService(
        synthetic_game.unit_of_work,
        small_vehicle_catalogue,
        synthetic_game_context.world,
    )
    with pytest.raises(ValueError, match="Reputation"):
        project_vehicle(fleet.purchase("daf_xg_plus_480"))
    player = project_player(synthetic_game.player_state())
    player.update(cash=500000, reputation=25)
    synthetic_game.state_repository.save_player(PlayerState(**player))
    vehicle = project_vehicle(fleet.purchase("daf_xg_plus_480"))
    rate = vehicle["operating_cost_eur_per_km"]
    assert vehicle["capacity_tons"] == 24.3
    assert synthetic_game.player_state().cash == 338000
    with (
        closing(sqlite3.connect(small_vehicle_catalogue.path)) as connection,
        connection,
    ):
        connection.execute(
            "UPDATE vehicle_balance SET operating_cost_eur_per_km_game=9"
        )
    assert (
        project_vehicle(synthetic_game.get_vehicle(vehicle["id"]))[
            "operating_cost_eur_per_km"
        ]
        == rate
    )
    before = project_player(synthetic_game.player_state())
    vehicles = [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ]
    with patch.object(
        synthetic_game.state_repository,
        "save_vehicle",
        side_effect=RuntimeError("persistence failed"),
    ):
        with pytest.raises(RuntimeError):
            project_vehicle(fleet.purchase("iveco_sway_500"))
    assert project_player(synthetic_game.player_state()) == before
    assert [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ] == vehicles


async def test_vehicle_quotes_and_legacy_snapshots_remain_compatible(
    synthetic_game_context,
    monkeypatch,
    synthetic_game,
    small_vehicle_catalogue,
):
    original = synthetic_game.state_repository.list_vehicles()[0]
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
    contract = first_berlin_contract(synthetic_game)
    synthetic_game.state_repository.save_vehicle(legacy)
    with pytest.raises(ValueError, match="Bestand"):
        await synthetic_game.quote_contract(contract["id"], "truck_01")
    synthetic_game.state_repository.save_vehicle(original)
    original._operating_cost_eur_per_km = 0.5
    synthetic_game.state_repository.save_vehicle(original)
    first = project_quote(
        await synthetic_game.quote_contract(contract["id"], "truck_01")
    )
    assert first["maintenance_eur_per_km"] == 0.078
    assert first["vehicle_id"] == "truck_01"
    vehicle = project_vehicle(
        FleetService(
            synthetic_game.unit_of_work,
            small_vehicle_catalogue,
            synthetic_game_context.world,
        ).purchase("iveco_sway_500")
    )
    quote = project_quote(
        await synthetic_game.quote_contract(contract["id"], vehicle["id"])
    )
    assert quote["operating_cost_eur"] == round(
        80 + quote["distance_km"] * quote["maintenance_eur_per_km"]
    )
    assert quote["payout_eur"] == first["payout_eur"]
    assert quote["operating_cost_eur"] == first["operating_cost_eur"]
    before = synthetic_game.player_state().cash
    trip = project_transport(
        await synthetic_game.dispatch(contract["id"], vehicle["id"])
    )
    assert trip["operating_cost_eur"] == quote["operating_cost_eur"]
    assert (
        synthetic_game.player_state().cash
        == before - quote["operating_cost_eur"]
    )
    # Old balances and models are not migrated by reinitialization.
    synthetic_game.state_repository.save_player(
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
        synthetic_game.state_repository.save_vehicle(legacy)
        synthetic_game.ensure_initial_state()
        assert synthetic_game.player_state().cash == 25000
        assert (
            project_vehicle(synthetic_game.get_vehicle("truck_01"))["model_id"]
            == model_id
        )
    # Already running transport economics are independent of the catalogue.
    set_game_clock(synthetic_game, lambda: trip["arrives_at"] + 1)
    assert synthetic_game.get_vehicle(vehicle["id"]).status == "enroute"
    assert synthetic_game.reconcile_arrival()
    assert synthetic_game.player_state().cash == 25000 + trip["payout_eur"]


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
        install_fake_routing_providers(app.state.game_runtime)
        prepare_client_market(client, app.state.game_runtime)
        contract = next(
            item
            for item in client.get(
                "/api/v1/contracts?vehicle_id=truck_01"
            ).json()["contracts"]
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
        cached = client.get("/api/v1/fleet/catalogue")
        assert cached.status_code == 200
        assert len(cached.json()["models"]) >= 8
        assert client.get("/api/v1/fleet").status_code == 200
        assert (
            client.get("/api/v1/dashboard").json()["player"]["cash"] == 175000
        )


def test_fleet_api_translates_catalogue_failures():
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


def test_fleet_builder_reuses_validated_runtime_catalogue(
    synthetic_runtime,
    synthetic_game,
):
    with synthetic_runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("new-account", "new-account", "test-only"),
        )
    fleet = build_fleet_service(synthetic_runtime, synthetic_game)
    assert len(project_catalogue(fleet.list_catalogue())["models"]) == len(
        synthetic_runtime.catalogue.list_models()
    )
    isolated = build_player_service(synthetic_runtime, "new-account")
    assert project_state(isolated.state())["player"]["cash"] == 175000


def test_catalogue_builder_default_path(tmp_path):
    settings = replace(
        make_settings(tmp_path),
        vehicle_catalogue_path=None,
        base_dir=Path(__file__).resolve().parents[1],
    )

    assert len(build_vehicle_catalogue(settings).list_models()) >= 8


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
    synthetic_game_context, database, synthetic_runtime, synthetic_game
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
    assert (
        starter["operating_cost_eur_per_km"] == model.operating_cost_eur_per_km
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
def test_catalogue_rejects_invalid_explicit_maintenance(
    small_vehicle_catalogue, value
):
    with (
        closing(sqlite3.connect(small_vehicle_catalogue.path)) as connection,
        connection,
    ):
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE vehicle_balance SET maintenance_eur_per_1000_km_game=?",
            (value,),
        )
    with pytest.raises(CatalogueError):
        small_vehicle_catalogue.list_models()


def test_catalogue_requires_explicit_maintenance_column(
    small_vehicle_catalogue,
):
    with (
        closing(sqlite3.connect(small_vehicle_catalogue.path)) as connection,
        connection,
    ):
        connection.execute(
            "ALTER TABLE vehicle_balance RENAME COLUMN "
            "maintenance_eur_per_1000_km_game TO unavailable_maintenance"
        )
    with pytest.raises(CatalogueError):
        small_vehicle_catalogue.list_models()
