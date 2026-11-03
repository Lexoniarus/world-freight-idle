"""SQLite world-catalogue repository and reference acceptance."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from app.domain.errors import WorldCatalogueError
from app.domain.world_scopes import WorldScope


def test_world_facility_mapping_preserves_sources_and_aliases(
    small_world_catalogue,
):
    facility = WorldScope(small_world_catalogue.read()).facility(
        "berlin_westhafen"
    )
    assert facility.sources[0].url == "https://example.test/facility/1"
    assert facility.aliases == ("berlin_westhafen",)


def test_world_facility_mapping_preserves_coordinate_evidence(
    small_world_catalogue,
):
    facility = WorldScope(small_world_catalogue.read()).facility(
        "berlin_westhafen"
    )
    evidence = facility.coordinate_evidence[0]
    assert evidence.url == "https://example.test/facility/1"
    assert evidence.precision == "official_facility_coordinate"
    assert evidence.provider == "tests"


def test_world_facility_mapping_preserves_documented_goods(
    small_world_catalogue,
):
    facility = WorldScope(small_world_catalogue.read()).facility(
        "berlin_westhafen"
    )
    assert facility.handled_goods[0].description == "Machine parts"
    assert facility.handled_goods[0].cargo_code == "01"


def test_reference_world_catalogue_preserves_identity_and_provenance(
    reference_world_catalogue,
):
    world = reference_world_catalogue.read()
    berlin = WorldScope(world).facility("berlin_westhafen")
    assert WorldScope(world).facility(berlin.facility_uid) is berlin
    assert berlin.company is not None
    assert (
        WorldScope(world).company(berlin.company.company_uid).company
        is berlin.company
    )
    assert berlin.is_routable() and berlin.has_verified_location()
    assert berlin.outbound_profiles() and berlin.inbound_profiles()
    assert len(world.facilities) == 559
    assert any(
        profile.evidence_type == "derived" and profile.source is None
        for facility in world.facilities
        for profile in facility.nhm_profiles
    )

    estimated = next(
        facility
        for facility in world.facilities
        if facility.geocoding_status == "estimated_for_simulation"
    )
    assert estimated.is_routable()
    assert not estimated.has_verified_location()
    assert estimated.coordinate_evidence


def test_nhm_ancestor_reader_rejects_invalid_hierarchy():
    from app.repositories.world_catalogue import read_nhm_ancestors

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE nhm_codes("
        "nhm_row_id INTEGER PRIMARY KEY, "
        "parent_row_id INTEGER)"
    )
    connection.execute("INSERT INTO nhm_codes VALUES(1, 1)")
    with pytest.raises(ValueError, match="Cyclic NHM hierarchy"):
        read_nhm_ancestors(connection)

    connection.execute("DELETE FROM nhm_codes")
    connection.execute("INSERT INTO nhm_codes VALUES(1, 999)")
    with pytest.raises(ValueError, match="Broken NHM parent reference"):
        read_nhm_ancestors(connection)
    connection.close()


def test_cached_world_catalogue_reads_source_once(small_world_catalogue):
    from app.repositories.cached_world_catalogue import CachedWorldCatalogue

    snapshot = small_world_catalogue.read()
    source = Mock()
    source.read.return_value = snapshot
    cached = CachedWorldCatalogue(source)
    assert cached.read() is snapshot
    assert cached.read() is snapshot
    source.read.assert_called_once_with()


def test_world_repository_readonly_and_cleanup(small_world_catalogue):
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
        small_world_catalogue.read()
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
    with (
        patch.object(module.sqlite3, "connect", side_effect=track),
        patch.object(
            module, "read_world_snapshot", side_effect=ValueError("invalid")
        ),
        pytest.raises(WorldCatalogueError),
    ):
        small_world_catalogue.read()
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[1].execute("SELECT 1")
    small_world_catalogue.path.unlink()
    with pytest.raises(WorldCatalogueError):
        small_world_catalogue.read()
    assert not small_world_catalogue.path.exists()
    small_world_catalogue.path.write_text("not sqlite", encoding="utf-8")
    with pytest.raises(WorldCatalogueError):
        small_world_catalogue.read()


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE metadata SET value='2.0.0' WHERE key='schema_version'",
        "DELETE FROM metadata WHERE key='operational_profile_system'",
        "DROP TABLE facility_nhm_profiles",
        "UPDATE facilities SET company_id=-1 WHERE facility_id=1",
        "UPDATE external_identifiers SET entity_id=-1",
        "DROP TRIGGER preserve_facility_uid; "
        "UPDATE facilities SET "
        "facility_uid='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaZ' "
        "WHERE facility_id=1",
        "UPDATE facility_sources SET source_url='' WHERE facility_id=1",
        "DELETE FROM facility_sources WHERE facility_id=1",
        "UPDATE sources SET base_url='' WHERE source_id IN "
        "(SELECT source_id FROM company_sources LIMIT 1)",
        "DELETE FROM nhm_market_profiles WHERE nhm_row_id="
        "(SELECT nhm_row_id FROM facility_nhm_profiles LIMIT 1)",
        "UPDATE nhm_codes SET is_numeric=0 WHERE nhm_row_id="
        "(SELECT nhm_row_id FROM facility_nhm_profiles LIMIT 1)",
        "UPDATE sources SET base_url='' WHERE source_id=(SELECT p.source_id "
        "FROM facility_nhm_profiles p WHERE p.evidence_type='official' "
        "AND p.source_id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM company_sources cs WHERE cs.source_id=p.source_id) "
        "LIMIT 1)",
        "UPDATE cargo_types SET nst_code='NHM:87' WHERE cargo_type_id="
        "(SELECT cargo_type_id FROM cargo_types LIMIT 1)",
    ],
)
def test_world_repository_rejects_incompatible_data(
    small_world_catalogue, mutation
):
    with (
        closing(sqlite3.connect(small_world_catalogue.path)) as connection,
        connection,
    ):
        connection.executescript(mutation)
    with pytest.raises(WorldCatalogueError):
        small_world_catalogue.read()


def test_world_uid_validation_and_duplicate_detection(
    small_world_catalogue,
):
    from app.repositories.world_catalogue import validate_uid

    with pytest.raises(ValueError):
        validate_uid("AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA")
    with (
        closing(sqlite3.connect(small_world_catalogue.path)) as connection,
        connection,
    ):
        connection.executescript("""
            DROP TRIGGER preserve_company_uid;
            DROP INDEX uq_company_uid;
            UPDATE companies SET company_uid=(
                SELECT company_uid FROM companies LIMIT 1
            );
        """)
    with pytest.raises(WorldCatalogueError, match="Weltkatalog"):
        small_world_catalogue.read()


def test_world_coordinates_require_matching_evidence(
    small_world_catalogue,
):
    before = small_world_catalogue.read()
    berlin = WorldScope(before).facility("berlin_westhafen")
    estimated = next(
        facility
        for facility in before.facilities
        if facility.geocoding_status == "estimated_for_simulation"
        and facility.coordinate_evidence[0].url.startswith("internal://")
    )
    with (
        closing(sqlite3.connect(small_world_catalogue.path)) as connection,
        connection,
    ):
        connection.execute(
            "UPDATE facility_geocoding_evidence SET source_url='invalid' "
            "WHERE facility_id=(SELECT facility_id FROM facilities "
            "WHERE facility_uid=?)",
            (berlin.facility_uid,),
        )
    after = WorldScope(small_world_catalogue.read()).facility(
        berlin.facility_uid
    )
    assert not after.is_routable()
    assert after.coordinates == berlin.coordinates
    assert estimated.is_routable()
    assert not estimated.has_verified_location()
    promoted = replace(estimated, geocoding_status="verified_coordinates")
    assert not promoted.is_routable()
    assert not promoted.has_verified_location()


def test_world_uids_survive_internal_primary_key_changes(
    small_world_catalogue,
):
    before = small_world_catalogue.read()
    with (
        closing(sqlite3.connect(small_world_catalogue.path)) as connection,
        connection,
    ):
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
    after = small_world_catalogue.read()
    assert after == before


def test_world_repository_rejects_half_null_coordinates(
    small_world_catalogue,
):
    with (
        closing(sqlite3.connect(small_world_catalogue.path)) as connection,
        connection,
    ):
        connection.executescript(
            "DROP TRIGGER coordinate_pair_update; "
            "PRAGMA ignore_check_constraints=ON; "
            "UPDATE facilities SET latitude=NULL WHERE longitude IS NOT NULL"
        )
    with pytest.raises(WorldCatalogueError):
        small_world_catalogue.read()


def test_world_repository_rejects_empty_catalogue(small_world_catalogue):
    with (
        closing(sqlite3.connect(small_world_catalogue.path)) as connection,
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
        small_world_catalogue.read()


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


def test_world_geography_shares_identities_and_rejects_broken_references(
    small_world_catalogue,
):
    snapshot = small_world_catalogue.read()
    facility = WorldScope(snapshot).facility("berlin_westhafen")
    city = facility.address.city
    assert city is next(
        c for c in snapshot.cities if c.city_uid == city.city_uid
    )
    assert city.country is next(
        c for c in snapshot.countries if c.code == "DE"
    )
    assert facility.company is not None
    assert facility.company.country is city.country
    location = facility.location_snapshot()
    assert location.city is city
    assert location.coordinates is facility.coordinates
    assert location.address == facility.address.display_text()
    for table, column, value in (
        ("countries", "name", ""),
        ("cities", "city_uid", "not-a-uuid"),
        ("cities", "country_code", "XX"),
    ):
        with closing(
            sqlite3.connect(small_world_catalogue.path)
        ) as connection:
            old = connection.execute(
                f"SELECT rowid,{column} FROM {table} LIMIT 1"
            ).fetchone()
            connection.execute(
                f"UPDATE {table} SET {column}=? WHERE rowid=?", (value, old[0])
            )
            connection.commit()
            with pytest.raises(WorldCatalogueError):
                small_world_catalogue.read()
            connection.execute(
                f"UPDATE {table} SET {column}=? WHERE rowid=?",
                (old[1], old[0]),
            )
            connection.commit()
