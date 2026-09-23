"""Offline upgrade preserves all historical facts and fails closed."""

import json
import sqlite3
import sys
from contextlib import closing
from unittest.mock import patch

import pytest

from app.domain.errors import PersistenceError, UnsupportedGameSchema
from app.repositories.database_backup import backup_database
from app.repositories.energy_upgrade import (
    SOURCE_SCHEMA,
    VehicleEnergyUpgradeRepository,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameStateRepository
from scripts.upgrade_vehicle_energy import main
from tests.transport_fixtures import add_transport


@pytest.fixture
def old_energy_state(game, database, tmp_path):
    trip = add_transport(game, departed_at=10, arrives_at=20)
    source = tmp_path / "pre-energy.db"
    with closing(sqlite3.connect(source)) as target:
        target.executescript(SOURCE_SCHEMA)
        target.execute(
            "CREATE TABLE sessions (token TEXT PRIMARY KEY, user_id TEXT)"
        )
        target.execute(
            "INSERT INTO sessions VALUES ('test-token','test-owner')"
        )
        with database.connect() as db:
            for table in (
                "users",
                "player_states",
                "owned_vehicles",
                "contract_offers",
                "transports",
            ):
                columns = [
                    row[1]
                    for row in target.execute(f"PRAGMA table_info({table})")
                ]
                for row in db.execute(f"SELECT * FROM {table}"):
                    values = dict(row)
                    if table == "transports":
                        doc = json.loads(values["transport_snapshot"])
                        doc["version"] = 1
                        del doc["data"]["journey"]
                        values["transport_snapshot"] = json.dumps(doc)
                    target.execute(
                        f"INSERT INTO {table} VALUES ({','.join('?' for _ in columns)})",
                        [values[key] for key in columns],
                    )
        target.commit()
    upgrade = VehicleEnergyUpgradeRepository(
        source, game.catalogue.list_models()
    )
    return source, upgrade, trip


def test_energy_upgrade_reconciles_accounts_sessions_and_history(
    old_energy_state, tmp_path
):
    source, upgrade, trip = old_energy_state
    original = source.read_bytes()
    report = upgrade.inspect()
    assert report == {
        "accounts": 1,
        "vehicles": 1,
        "transports": 1,
        "sessions": 1,
    }
    with pytest.raises(UnsupportedGameSchema):
        SqliteGameDatabase(source).initialize()
    backup_database(source, tmp_path / "backup.db")
    output = tmp_path / "upgraded.db"
    assert upgrade.upgrade_to(output) == report
    db = SqliteGameDatabase(output)
    db.initialize()
    repo = SqliteGameStateRepository(db, "test-owner")
    vehicle = repo.list_vehicles()[0]
    assert vehicle.energy_level == vehicle.energy.capacity == 1010
    assert repo.list_transports() == (trip,)
    assert repo.list_transports()[0].journey.energy is None
    with db.connect() as connection:
        assert tuple(
            connection.execute("SELECT * FROM sessions").fetchone()
        ) == ("test-token", "test-owner")
        assert (
            connection.execute("SELECT version FROM game_schema").fetchone()[0]
            == "1.1.0"
        )
        document = json.loads(
            connection.execute(
                "SELECT transport_snapshot FROM transports"
            ).fetchone()[0]
        )
        assert document["version"] == 2
    with pytest.raises(FileExistsError):
        upgrade.upgrade_to(output)
    with pytest.raises(PersistenceError):
        VehicleEnergyUpgradeRepository(
            output, tuple(upgrade.models.values())
        ).inspect()
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "fault",
    [
        "model",
        "snapshot",
        "capacity",
        "table",
        "guard",
        "version",
        "integrity",
        "ownership",
        "null",
        "list",
        "data",
        "boolean",
    ],
)
def test_energy_upgrade_rejects_invalid_source_without_output(
    old_energy_state, tmp_path, fault
):
    source, upgrade, _ = old_energy_state
    with closing(sqlite3.connect(source)) as db:
        if fault == "model":
            db.execute("UPDATE owned_vehicles SET model_id='missing'")
        elif fault == "snapshot":
            db.execute("UPDATE transports SET transport_snapshot='{}'")
        elif fault == "capacity":
            db.execute("PRAGMA ignore_check_constraints=ON")
            db.execute("UPDATE owned_vehicles SET capacity_tons=-1")
        elif fault == "table":
            db.execute("CREATE TABLE unexpected (value TEXT)")
        elif fault == "guard":
            db.execute("DROP TRIGGER retain_settlement")
        elif fault == "integrity":
            db.execute("PRAGMA ignore_check_constraints=ON")
            db.execute("UPDATE player_states SET cash=-1")
        elif fault == "ownership":
            db.execute("UPDATE owned_vehicles SET user_id='unknown'")
        elif fault in {"null", "list", "data", "boolean"}:
            document = json.loads(
                db.execute(
                    "SELECT transport_snapshot FROM transports"
                ).fetchone()[0]
            )
            if fault == "null":
                document = None
            elif fault == "list":
                document = []
            elif fault == "data":
                document["data"] = None
            else:
                document["version"] = True
            db.execute(
                "UPDATE transports SET transport_snapshot=?",
                (json.dumps(document),),
            )
        else:
            db.execute("UPDATE game_schema SET version='0.9.0'")
        db.commit()
    original = source.read_bytes()
    output = tmp_path / "failed.db"
    with pytest.raises(PersistenceError):
        upgrade.inspect()
    with pytest.raises(PersistenceError):
        upgrade.upgrade_to(output)
    assert not output.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize("fault", ["values", "integrity", "ownership"])
def test_energy_upgrade_reconciliation_failure_removes_target(
    old_energy_state, tmp_path, fault, caplog
):
    source, upgrade, _ = old_energy_state
    original = source.read_bytes()
    output = tmp_path / "failed.db"
    write = upgrade._write_inventory

    def corrupt_output(db, inventory):
        write(db, inventory)
        with db.connect() as connection:
            if fault == "integrity":
                connection.execute("PRAGMA ignore_check_constraints=ON")
                connection.execute("UPDATE player_states SET cash=-1")
            elif fault == "ownership":
                connection.execute("PRAGMA foreign_keys=OFF")
                connection.execute(
                    "UPDATE owned_vehicles SET user_id='unknown'"
                )
            else:
                connection.execute("UPDATE player_states SET cash=cash+1")

    with patch.object(upgrade, "_write_inventory", side_effect=corrupt_output):
        with pytest.raises(PersistenceError):
            upgrade.upgrade_to(output)
    assert not output.exists()
    assert source.read_bytes() == original
    assert any(
        getattr(record, "event", None) == "state.energy_upgrade_rolled_back"
        for record in caplog.records
    )


def test_energy_upgrade_cli_backs_up_before_building(
    old_energy_state, tmp_path, monkeypatch, capsys
):
    source, upgrade, _ = old_energy_state
    output, backup = tmp_path / "output.db", tmp_path / "backup.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "upgrade",
            "--source",
            str(source),
            "--output",
            str(output),
            "--backup",
            str(backup),
        ],
    )
    with (
        patch(
            "scripts.upgrade_vehicle_energy.backup_database",
            side_effect=OSError("disk"),
        ),
        patch("scripts.upgrade_vehicle_energy.build_energy_upgrade") as build,
    ):
        with pytest.raises(OSError):
            main()
        build.assert_not_called()
    with patch(
        "scripts.upgrade_vehicle_energy.build_energy_upgrade",
        return_value=upgrade,
    ):
        main()
    assert backup.exists() and output.exists()
    assert json.loads(capsys.readouterr().out)["vehicles"] == 1
    with pytest.raises(SystemExit):
        main()

    monkeypatch.setattr(
        sys, "argv", ["upgrade", "--source", str(source), "--check"]
    )
    with (
        patch(
            "scripts.upgrade_vehicle_energy.build_energy_upgrade",
            return_value=upgrade,
        ),
        patch("scripts.upgrade_vehicle_energy.backup_database") as backup_call,
    ):
        main()
    backup_call.assert_not_called()
    assert json.loads(capsys.readouterr().out)["vehicles"] == 1


def test_energy_upgrade_builder_requires_catalogue(tmp_path):
    from dataclasses import replace

    from app.bootstrap import build_energy_upgrade
    from app.config import Settings
    from app.domain.errors import CatalogueError

    settings = Settings.from_env()
    assert build_energy_upgrade(tmp_path / "source.db", settings).models
    with pytest.raises(CatalogueError):
        build_energy_upgrade(
            tmp_path / "source.db",
            replace(settings, vehicle_catalogue_path=tmp_path / "missing.db"),
        )
