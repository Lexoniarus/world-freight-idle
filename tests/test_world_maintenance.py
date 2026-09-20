"""Offline upgrade preserves UUIDs and rolls back invalid evidence."""

import copy
import json
import runpy
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest

from app.bootstrap import build_world_maintenance_service
from app.repositories.database_backup import backup_database
from app.repositories.world_maintenance import (
    WorldMaintenanceRepository,
    insert_terminal_nhm_profiles,
)
from app.services.world_maintenance import validate_legacy_evidence

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence():
    return json.loads(
        (ROOT / "docs/data/legacy-facilities.json").read_text(encoding="utf-8")
    )


def downgrade_fixture(path):
    """Derive the delivered v2 shape from a temporary v3 copy."""
    with closing(sqlite3.connect(path)) as connection, connection:
        facilities = tuple(
            row[0]
            for row in connection.execute(
                "SELECT facility_id FROM facilities JOIN facility_aliases USING(facility_uid)"
            )
        )
        companies = tuple(
            row[0]
            for row in connection.execute(
                "SELECT company_id FROM facilities JOIN facility_aliases USING(facility_uid)"
            )
        )
        if facilities:
            placeholders = ",".join("?" for _ in facilities)
            connection.execute(
                "DELETE FROM facility_handled_goods_nhm "
                "WHERE handled_goods_id IN ("
                "SELECT handled_goods_id "
                "FROM facility_handled_goods "
                f"WHERE facility_id IN ({placeholders})"
                ")",
                facilities,
            )
        connection.execute("DROP TABLE facility_aliases")
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        ]
        for table in tables:
            columns = {
                row[1]
                for row in connection.execute(f'PRAGMA table_info("{table}")')
            }
            for column, identifiers in (
                ("facility_id", facilities),
                ("company_id", companies),
            ):
                if column in columns:
                    placeholders = ",".join("?" for _ in identifiers)
                    connection.execute(
                        f'DELETE FROM "{table}" WHERE {column} IN ({placeholders})',
                        identifiers,
                    )
        for (trigger,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall():
            connection.execute(f'DROP TRIGGER "{trigger}"')
        for table, kind in (
            ("companies", "company"),
            ("facilities", "facility"),
        ):
            connection.execute(f"DROP INDEX uq_{kind}_uid")
            connection.execute(f"ALTER TABLE {table} DROP COLUMN {kind}_uid")
        connection.execute(
            "UPDATE metadata SET value='2.0.0' WHERE key='schema_version'"
        )


def test_world_preparation_is_atomic_idempotent_and_enforces_identity(
    world_catalogue, evidence
):
    downgrade_fixture(world_catalogue.path)
    service = build_world_maintenance_service(world_catalogue.path)
    service.prepare(evidence)
    first = world_catalogue.read()
    assert len(first.facilities) == 155
    service.prepare(evidence)
    assert world_catalogue.read() == first
    with closing(sqlite3.connect(world_catalogue.path)) as connection:
        for statement in (
            "UPDATE facilities SET facility_uid=NULL",
            "UPDATE facilities SET facility_uid='11111111-1111-1111-1111-111111111111'",
            "UPDATE facilities SET latitude=NULL WHERE longitude IS NOT NULL",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)
            connection.rollback()
    with pytest.raises(ValueError):
        service.prepare(evidence[:3])
    assert world_catalogue.read() == first


def test_world_preparation_rolls_back_schema_and_rejects_unready_alias(
    world_catalogue, evidence
):
    downgrade_fixture(world_catalogue.path)
    broken = copy.deepcopy(evidence)
    broken[-1]["cargo_code"] = "missing"
    repository = WorldMaintenanceRepository(world_catalogue.path)
    with pytest.raises(TypeError):
        repository.upgrade(broken)
    with closing(sqlite3.connect(world_catalogue.path)) as connection:
        assert (
            dict(connection.execute("SELECT key,value FROM metadata"))[
                "schema_version"
            ]
            == "2.0.0"
        )
        assert "facility_uid" not in {
            r[1] for r in connection.execute("PRAGMA table_info(facilities)")
        }
    repository.upgrade(evidence)
    with (
        closing(sqlite3.connect(world_catalogue.path)) as connection,
        connection,
    ):
        connection.execute(
            "DELETE FROM facility_geocoding_evidence WHERE facility_id IN (SELECT facility_id FROM facilities JOIN facility_aliases USING(facility_uid))"
        )
    with pytest.raises(ValueError, match="market ready"):
        repository.upgrade(evidence)
    with (
        closing(sqlite3.connect(world_catalogue.path)) as connection,
        connection,
    ):
        connection.execute(
            "UPDATE metadata SET value='99' WHERE key='schema_version'"
        )
    with pytest.raises(ValueError, match="Unsupported"):
        repository.upgrade(evidence)


@pytest.mark.parametrize(
    "field,value",
    [
        ("company", ""),
        ("source_url", "file://bad"),
        ("precision", "city"),
        ("lat", 91),
        ("lon", float("nan")),
        ("lat", True),
    ],
)
def test_world_evidence_rejects_unverified_candidates(evidence, field, value):
    validate_legacy_evidence(evidence[0])
    evidence[0][field] = value
    with pytest.raises(ValueError):
        validate_legacy_evidence(evidence[0])


def test_terminal_nhm_profile_rejects_missing_chapters():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE nhm_codes("
        "nhm_row_id INTEGER PRIMARY KEY, code TEXT NOT NULL)"
    )
    with pytest.raises(ValueError, match="Missing NHM terminal chapter"):
        insert_terminal_nhm_profiles(connection, 1, 1)
    connection.close()


def test_world_prepare_cli_requires_backup(
    world_catalogue, tmp_path, monkeypatch
):
    backup = tmp_path / "backup.sqlite3"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare",
            "--catalogue",
            str(world_catalogue.path),
            "--backup",
            str(backup),
            "--evidence",
            str(ROOT / "docs/data/legacy-facilities.json"),
        ],
    )
    runpy.run_path(
        str(ROOT / "scripts/prepare_world_catalogue.py"), run_name="__main__"
    )
    with closing(sqlite3.connect(backup)) as connection:
        assert (
            connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        )
    with patch("app.bootstrap.build_world_maintenance_service") as build:
        with pytest.raises(FileExistsError):
            runpy.run_path(
                str(ROOT / "scripts/prepare_world_catalogue.py"),
                run_name="__main__",
            )
        build.assert_not_called()
    with pytest.raises(FileExistsError):
        backup_database(world_catalogue.path, backup)
