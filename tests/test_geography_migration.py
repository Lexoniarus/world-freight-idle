"""Reference migration uses explicit assignments and a separate output."""

import copy
import json
import sqlite3
from contextlib import closing
from unittest.mock import MagicMock, patch

import pytest

from app.bootstrap import build_geography_migration
from app.repositories.database_backup import backup_database
from app.repositories.world_geography import (
    catalogue_identities,
    rebuild_geographical_table,
    validate_normalized_geography,
    validate_source_geography,
)
from app.services.world_geography import validate_geography_mapping
from scripts.normalize_world_catalogue import main


@pytest.fixture
def geography_source(tmp_path):
    path = tmp_path / "source.sqlite3"
    document = {
        "version": 1,
        "source_schema": "3.0.0",
        "source_data_version": "test",
        "countries": [{"code": "DE", "name": "Germany"}],
        "cities": [
            {
                "city_uid": "a0000000-0000-4000-8000-000000000001",
                "name": "Berlin",
                "country_code": "DE",
                "region": None,
            }
        ],
        "facilities": [
            {
                "facility_uid": "f0000000-0000-4000-8000-000000000001",
                "city_uid": "a0000000-0000-4000-8000-000000000001",
                "source_country": "DE",
                "source_city": "Berlin",
                "source_region": None,
            }
        ],
    }
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
            INSERT INTO metadata VALUES('schema_version','3.0.0');
            INSERT INTO metadata VALUES('data_version','test');
            CREATE TABLE companies(company_id INTEGER PRIMARY KEY,
                country_code TEXT NOT NULL, company_uid TEXT);
            CREATE UNIQUE INDEX uq_company_uid ON companies(company_uid);
            INSERT INTO companies VALUES(7,'DE','company-identity');
            CREATE TABLE facilities(facility_id INTEGER PRIMARY KEY,
                company_id INTEGER REFERENCES companies(company_id),
                city TEXT NOT NULL, state_region TEXT,
                country_code TEXT NOT NULL, latitude REAL, longitude REAL,
                facility_uid TEXT, CHECK (
                    (latitude IS NULL AND longitude IS NULL) OR
                    (latitude BETWEEN -90 AND 90 AND
                    longitude BETWEEN -180 AND 180)));
            CREATE UNIQUE INDEX uq_facility_uid ON facilities(facility_uid);
            CREATE TABLE evidence(facility_id INTEGER
                REFERENCES facilities(facility_id),note TEXT);
            CREATE VIEW facility_catalog_full AS
                SELECT f.city, f.country_code, f.facility_uid
                FROM facilities AS f;
            CREATE TRIGGER evidence_guard BEFORE INSERT ON evidence
                WHEN NEW.note IS NULL BEGIN
                SELECT RAISE(ABORT,'missing evidence'); END;
        """)
        db.execute(
            "INSERT INTO facilities VALUES(8,7,'Berlin',NULL,'DE',52,13,?)",
            (document["facilities"][0]["facility_uid"],),
        )
        db.execute("INSERT INTO evidence VALUES(8,'unchanged')")
    return path, document


def test_geography_migration_reconciles_identity_and_is_idempotent(
    geography_source,
    tmp_path,
):
    source, document = geography_source
    backup = tmp_path / "backup.sqlite3"
    target = tmp_path / "normalized.sqlite3"
    before = source.read_bytes()
    backup_database(source, backup)
    mapping = validate_geography_mapping(document)
    migration = build_geography_migration(backup, target)
    migration.normalize(mapping)
    first = target.read_bytes()
    migration.normalize(mapping)
    assert target.read_bytes() == first
    assert source.read_bytes() == before
    with closing(sqlite3.connect(target)) as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT * FROM evidence").fetchall() == [
            (8, "unchanged")
        ]
        assert db.execute(
            "SELECT city,country_code FROM facility_catalog_full"
        ).fetchone() == ("Berlin", "DE")
        assert db.execute(
            "SELECT latitude,longitude FROM facilities"
        ).fetchone() == (52, 13)
        columns = {r[1] for r in db.execute("PRAGMA table_info(facilities)")}
        assert not {"city", "country_code", "state_region"} & columns
        for sql in (
            "UPDATE facilities SET city_uid=NULL",
            "UPDATE facilities SET latitude=NULL",
            "UPDATE facilities SET facility_uid=NULL",
            "INSERT INTO evidence VALUES(8,NULL)",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
            db.rollback()
    with pytest.raises(ValueError):
        build_geography_migration(source, source)
    with closing(sqlite3.connect(target)) as db, db:
        db.execute("UPDATE cities SET name='changed'")
    changed = target.read_bytes()
    with pytest.raises(ValueError, match="differs"):
        migration.normalize(mapping)
    assert target.read_bytes() == changed


def test_geography_mapping_rejects_duplicate_or_changed_assignments(
    geography_source,
    tmp_path,
):
    source, document = geography_source
    for field in ("countries", "cities", "facilities"):
        broken = copy.deepcopy(document)
        broken[field].append(broken[field][0])
        with pytest.raises(ValueError):
            validate_geography_mapping(broken)
    for changes in ({"version": 2}, {"version": True}, {"cities": []}):
        with pytest.raises((ValueError, KeyError)):
            validate_geography_mapping({**document, **changes})
    for changes in (
        {"source_city": "elsewhere"},
        {"city_uid": "unknown"},
        {"facility_uid": "12"},
        {"facility_uid": "F0000000-0000-4000-8000-000000000001"},
        {"source_region": "unreviewed"},
    ):
        broken = copy.deepcopy(document)
        broken["facilities"][0].update(changes)
        with pytest.raises((ValueError, KeyError)):
            validate_geography_mapping(broken)
    mapping = validate_geography_mapping(document)
    target = tmp_path / "output.sqlite3"
    with closing(sqlite3.connect(source)) as db, db:
        db.execute("UPDATE facilities SET city='changed'")
    with pytest.raises(ValueError, match="inventory"):
        build_geography_migration(source, target).normalize(mapping)
    assert not target.exists()
    with closing(sqlite3.connect(source)) as db, db:
        db.execute("UPDATE metadata SET value='unknown'")
    with pytest.raises(ValueError, match="revision"):
        build_geography_migration(source, target).normalize(mapping)


def test_geography_migration_rolls_back_and_requires_backup(
    geography_source,
    tmp_path,
    monkeypatch,
):
    source, document = geography_source
    before = source.read_bytes()
    target = tmp_path / "output.sqlite3"
    mapping = validate_geography_mapping(document)
    with patch(
        "app.repositories.world_geography.rebuild_geographical_table",
        side_effect=RuntimeError("write failed"),
    ):
        with pytest.raises(RuntimeError):
            build_geography_migration(source, target).normalize(mapping)
    assert not target.exists() and source.read_bytes() == before
    with closing(sqlite3.connect(source)) as db:
        with pytest.raises(ValueError):
            rebuild_geographical_table(db, "unrelated")
    manifest = tmp_path / "mapping.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    backup = tmp_path / "backup.sqlite3"
    monkeypatch.setattr(
        "sys.argv",
        [
            "normalize",
            "--catalogue",
            str(source),
            "--backup",
            str(backup),
            "--output",
            str(target),
            "--mapping",
            str(manifest),
        ],
    )
    with (
        patch(
            "scripts.normalize_world_catalogue.backup_database",
            side_effect=OSError("backup failed"),
        ),
        patch(
            "scripts.normalize_world_catalogue.build_geography_migration"
        ) as b,
    ):
        with pytest.raises(OSError):
            main()
        b.assert_not_called()
    assert not target.exists()
    main()
    assert backup.exists() and target.exists()
    assert source.read_bytes() == before


def test_geography_rejects_broken_references_and_failed_integrity(
    geography_source, tmp_path
):
    source, document = geography_source
    mapping = validate_geography_mapping(document)
    target = tmp_path / "normalized.sqlite3"
    build_geography_migration(source, target).normalize(mapping)
    for path, normalized in ((source, False), (target, True)):
        with closing(sqlite3.connect(path)) as db:
            identities = catalogue_identities(db)
            db.execute("UPDATE evidence SET facility_id=999")
            with pytest.raises(ValueError, match="broken references"):
                if normalized:
                    validate_normalized_geography(db, mapping, identities)
                else:
                    validate_source_geography(db, mapping)
            db.rollback()
    with closing(sqlite3.connect(target)) as real:
        connection = MagicMock(wraps=real)

        def execute(sql, *args):
            if sql == "PRAGMA integrity_check":
                result = MagicMock()
                result.fetchone.return_value = ("damaged index",)
                return result
            return real.execute(sql, *args)

        connection.execute.side_effect = execute
        with pytest.raises(ValueError, match="integrity check failed"):
            validate_normalized_geography(connection, mapping, identities)
