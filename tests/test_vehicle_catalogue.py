"""SQLite vehicle-catalogue integrity and reference acceptance."""

import hashlib
import math
import sqlite3
from contextlib import closing

import pytest

from app.domain.energy import EnergyProfile
from app.domain.errors import CatalogueError
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue


def test_catalogue_projects_all_offers_without_writing(
    reference_vehicle_catalogue,
):
    before = hashlib.sha256(
        reference_vehicle_catalogue.path.read_bytes()
    ).digest()
    models = reference_vehicle_catalogue.list_models()
    assert len(models) >= 8
    assert [(model.price_eur, model.id) for model in models] == sorted(
        (model.price_eur, model.id) for model in models
    )
    first = next(model for model in models if model.id == "iveco_sway_500")
    assert first.price_eur == 149000
    assert first.capacity_tons == 24.2
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
        "electric",
        "kWh",
        600,
        103,
        35,
        0.1,
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
                "version": (
                    "UPDATE catalog_metadata SET value='0' "
                    "WHERE key='schema_version'"
                ),
                "references": (
                    "UPDATE vehicle_models SET manufacturer_id='missing'"
                ),
                "empty": "DELETE FROM vehicle_sources",
                "incomplete": "DELETE FROM vehicle_balance",
                "text": (
                    "UPDATE manufacturers SET name='' "
                    "WHERE manufacturer_id='daf'"
                ),
                "integer": (
                    "UPDATE vehicle_balance SET purchase_price_eur_game=1.5"
                ),
                "number": (
                    "UPDATE vehicle_balance "
                    "SET operating_cost_eur_per_km_game='oops'"
                ),
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


@pytest.mark.parametrize("value", [-1, math.inf, "invalid"])
def test_catalogue_rejects_invalid_explicit_maintenance(
    small_vehicle_catalogue,
    value,
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
