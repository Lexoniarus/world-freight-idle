"""Reference provenance, identities, read-only boundaries and map filtering."""

import sqlite3
from contextlib import closing
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch

import pytest

from app.domain.errors import WorldCatalogueError
from app.domain.world import FacilityQuery


def test_world_snapshot_identity_provenance_and_query(world_catalogue):
    world = world_catalogue.read()
    berlin = world.get_facility("berlin_westhafen")
    assert world.get_facility(berlin.facility_uid) is berlin
    assert berlin.company is not None
    assert world.get_company(berlin.company.company_uid) is berlin.company
    assert berlin.is_routable() and berlin.outbound_cargo()
    assert len(world.facilities) == 155
    assert len(world.query(FacilityQuery())) == 43
    with pytest.raises(KeyError):
        world.get_facility("1")
    with pytest.raises(KeyError):
        world.get_company("1")
    ambiguous = replace(
        world, facilities=(berlin, replace(berlin, facility_uid="other"))
    )
    with pytest.raises(KeyError, match="ambiguous"):
        ambiguous.get_facility("berlin_westhafen")
    with pytest.raises(FrozenInstanceError):
        setattr(berlin, "label", "changed")
    serialized = berlin.to_dict()
    serialized["company"]["display_name"] = "changed"
    assert berlin.company.display_name != "changed"
    assert serialized["id"] == berlin.facility_uid
    assert "facility_id" not in serialized and "company_id" not in serialized
    assert replace(berlin, company=None).to_dict()["company_uid"] is None
    for field, value in (
        ("lat", None),
        ("lon", float("inf")),
        ("lat", 91),
        ("coordinate_evidence", ()),
        ("geocoding_status", "candidate"),
    ):
        assert not replace(berlin, **{field: value}).is_routable()
    cargo = berlin.outbound_cargo()[0]
    for item in (
        replace(cargo, standard=False),
        replace(cargo, role="input"),
        replace(cargo, evidence_type="assumed"),
    ):
        assert not replace(berlin, cargo=(item,)).outbound_cargo()
    assert not FacilityQuery().includes(replace(berlin, lat=None))
    dateline = FacilityQuery.parse("170,-10,-170,10")
    assert dateline.includes(replace(berlin, lat=0, lon=179))
    assert dateline.includes(replace(berlin, lat=0, lon=-179))
    assert not dateline.includes(replace(berlin, lat=0, lon=0))
    assert FacilityQuery.parse("13,52,14,53").includes(berlin)
    assert not FacilityQuery.parse("0,0,1,1").includes(berlin)
    for bounds in ("", "0,1,2", "nan,0,1,2", "181,0,1,2", "0,4,1,2"):
        with pytest.raises(ValueError):
            FacilityQuery.parse(bounds)


def test_world_repository_readonly_and_cleanup(world_catalogue):
    original = sqlite3.connect
    connections = []

    def track(*args, **kwargs):
        connection = original(*args, **kwargs)
        connections.append(connection)
        return connection

    from app.repositories import world_catalogue as module

    original_reader = module.read_world_snapshot

    def read_and_check(connection):
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM facilities")
        return original_reader(connection)

    with (
        patch.object(module.sqlite3, "connect", side_effect=track),
        patch.object(
            module, "read_world_snapshot", side_effect=read_and_check
        ),
    ):
        world_catalogue.read()
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
    with (
        patch.object(module.sqlite3, "connect", side_effect=track),
        patch.object(
            module, "read_world_snapshot", side_effect=ValueError("invalid")
        ),
        pytest.raises(WorldCatalogueError),
    ):
        world_catalogue.read()
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[1].execute("SELECT 1")
    world_catalogue.path.unlink()
    with pytest.raises(WorldCatalogueError):
        world_catalogue.read()
    assert not world_catalogue.path.exists()
    world_catalogue.path.write_text("not sqlite", encoding="utf-8")
    with pytest.raises(WorldCatalogueError):
        world_catalogue.read()


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE metadata SET value='2.0.0' WHERE key='schema_version'",
        "DELETE FROM metadata WHERE key='data_version'",
        "UPDATE facilities SET company_id=-1 WHERE facility_id=1",
        "UPDATE external_identifiers SET entity_id=-1",
        "DROP TRIGGER preserve_facility_uid; UPDATE facilities SET facility_uid='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaZ' WHERE facility_id=1",
        "UPDATE facility_sources SET source_url='' WHERE facility_id=1",
        "DELETE FROM facility_sources WHERE facility_id=1",
        "UPDATE sources SET base_url=''",
        "DELETE FROM facility_aliases; DELETE FROM facilities; DELETE FROM external_identifiers; DELETE FROM facility_sources; DELETE FROM facility_geocoding_evidence; DELETE FROM facility_cargo_profiles; DELETE FROM facility_handled_goods; DELETE FROM facility_images",
    ],
)
def test_world_repository_rejects_incompatible_data(world_catalogue, mutation):
    with (
        closing(sqlite3.connect(world_catalogue.path)) as connection,
        connection,
    ):
        connection.executescript(mutation)
    with pytest.raises(WorldCatalogueError):
        world_catalogue.read()


def test_world_uid_validation_and_duplicate_detection(world_catalogue):
    from app.repositories.world_catalogue import validate_uid

    with pytest.raises(ValueError):
        validate_uid("AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA")
    with (
        closing(sqlite3.connect(world_catalogue.path)) as connection,
        connection,
    ):
        connection.executescript("""
            DROP TRIGGER preserve_company_uid;
            DROP INDEX uq_company_uid;
            UPDATE companies SET company_uid=(SELECT company_uid FROM companies LIMIT 1);
        """)
    with pytest.raises(WorldCatalogueError, match="Weltkatalog"):
        world_catalogue.read()


def test_world_coordinates_require_matching_evidence(world_catalogue):
    before = world_catalogue.read()
    berlin = before.get_facility("berlin_westhafen")
    with (
        closing(sqlite3.connect(world_catalogue.path)) as connection,
        connection,
    ):
        connection.execute(
            "UPDATE facility_geocoding_evidence SET source_url='invalid' WHERE facility_id=(SELECT facility_id FROM facilities WHERE facility_uid=?)",
            (berlin.facility_uid,),
        )
    after = world_catalogue.read().get_facility(berlin.facility_uid)
    assert not after.is_routable()
    assert after.lat == berlin.lat


def test_world_uids_survive_internal_primary_key_changes(world_catalogue):
    before = world_catalogue.read()
    with (
        closing(sqlite3.connect(world_catalogue.path)) as connection,
        connection,
    ):
        # Offline importer explicitly preserves UIDs and remaps internal FKs.
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
            for column in ("company_id", "facility_id"):
                if column in columns:
                    connection.execute(
                        f'UPDATE "{table}" SET {column}={column}+10000'
                    )
        connection.execute(
            "UPDATE external_identifiers SET entity_id=entity_id+10000"
        )
    after = world_catalogue.read()
    assert after == before


def test_delivery_requires_verified_catalogue_endpoint(world_catalogue):
    from unittest.mock import Mock

    from app.services.fleet import resolve_delivery_facility

    snapshot = world_catalogue.read()
    assert resolve_delivery_facility(world_catalogue)["handled_goods"]
    for facilities in (
        (),
        (
            replace(
                snapshot.get_facility("berlin_westhafen"),
                coordinate_evidence=(),
            ),
        ),
    ):
        world = Mock(
            read=Mock(return_value=replace(snapshot, facilities=facilities))
        )
        with pytest.raises(WorldCatalogueError):
            resolve_delivery_facility(world)


def test_world_repository_rejects_half_null_coordinates(world_catalogue):
    with (
        closing(sqlite3.connect(world_catalogue.path)) as connection,
        connection,
    ):
        connection.executescript(
            "DROP TRIGGER coordinate_pair_update; UPDATE facilities SET latitude=NULL WHERE longitude IS NOT NULL"
        )
    with pytest.raises(WorldCatalogueError):
        world_catalogue.read()


def test_world_repository_rejects_empty_catalogue(world_catalogue):
    with (
        closing(sqlite3.connect(world_catalogue.path)) as connection,
        connection,
    ):
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        ]
        for table in tables:
            if table != "metadata":
                connection.execute(f'DELETE FROM "{table}"')
    with pytest.raises(WorldCatalogueError):
        world_catalogue.read()


def test_world_catalogue_is_packaged_independently_of_player_state(
    tmp_path, monkeypatch
):
    from pathlib import Path

    from app.bootstrap import build_world_catalogue
    from app.config import Settings

    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("WORLD_CATALOGUE_PATH", raising=False)
    settings = Settings.from_env(root)
    assert settings.db_path.parent == tmp_path
    assert build_world_catalogue(settings).read().facilities
    for name in (".gitignore", ".dockerignore"):
        assert "!data/world_freight_company_facility_mvp.sqlite3" in (
            root / name
        ).read_text(encoding="utf-8")
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "world_freight_company_facility_mvp.sqlite3:ro" in compose
    monkeypatch.setenv(
        "WORLD_CATALOGUE_PATH", str(tmp_path / "missing.sqlite3")
    )
    with pytest.raises(WorldCatalogueError):
        build_world_catalogue(Settings.from_env(root)).read()
