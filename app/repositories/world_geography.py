"""Offline normalization of a backed-up catalogue into a separate file."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from app.domain.geography_migration import GeographyMapping
from app.repositories.database_backup import backup_database

LOGGER = logging.getLogger(__name__)


class WorldGeographyRepository:
    """Own one immutable source backup and an exclusively created output."""

    def __init__(self, backup: Path, target: Path) -> None:
        if backup.resolve() == target.resolve():
            raise ValueError("Catalogue source and output must differ.")
        self._backup = backup
        self._target = target

    def normalize(self, mapping: GeographyMapping) -> None:
        """Validate source assignments before creating the normalized file."""
        with closing(
            sqlite3.connect(
                self._backup.resolve().as_uri() + "?mode=ro", uri=True
            )
        ) as source:
            validate_source_geography(source, mapping)
            identities = catalogue_identities(source)
        if self._target.exists():
            with closing(
                sqlite3.connect(
                    self._target.resolve().as_uri() + "?mode=ro", uri=True
                )
            ) as target:
                validate_normalized_geography(target, mapping, identities)
            return
        backup_database(self._backup, self._target)
        try:
            with closing(sqlite3.connect(self._target)) as target:
                target.execute("PRAGMA foreign_keys=OFF")
                with target:
                    target.execute("BEGIN IMMEDIATE")
                    normalize_geography_tables(target, mapping)
                    validate_normalized_geography(target, mapping, identities)
        except Exception:
            self._target.unlink()
            LOGGER.exception(
                "World geography migration rolled back",
                extra={"event": "world.geography_migration_failed"},
            )
            raise
        LOGGER.info(
            "World geography normalized",
            extra={
                "event": "world.geography_migrated",
                "data": {
                    "schema_version": "4.0.0",
                    "mapping_version": mapping.version,
                    "cities": len(mapping.cities),
                    "facilities": len(mapping.facilities),
                },
            },
        )


def catalogue_identities(connection: sqlite3.Connection) -> tuple:
    """Read stable company/facility identities independently of row IDs."""
    return (
        tuple(
            connection.execute(
                "SELECT company_uid FROM companies ORDER BY company_uid"
            )
        ),
        tuple(
            connection.execute(
                "SELECT facility_uid FROM facilities ORDER BY facility_uid"
            )
        ),
    )


def validate_source_geography(
    connection: sqlite3.Connection, mapping: GeographyMapping
) -> None:
    """Reject changed source facts or an incomplete inventory."""
    metadata = dict(connection.execute("SELECT key,value FROM metadata"))
    if (
        metadata.get("schema_version") != "3.0.0"
        or metadata.get("data_version") != mapping.source_data_version
    ):
        raise ValueError("Source catalogue does not match mapping revision.")
    actual = set(
        connection.execute(
            "SELECT facility_uid,country_code,city,state_region "
            "FROM facilities"
        )
    )
    expected = {
        (a.facility_uid, a.source_country, a.source_city, a.source_region)
        for a in mapping.facilities
    }
    if actual != expected:
        raise ValueError("Facility inventory differs from reviewed mapping.")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Source catalogue has broken references.")


def normalize_geography_tables(
    connection: sqlite3.Connection, mapping: GeographyMapping
) -> None:
    """Normalize geography in the caller's write transaction."""
    triggers = connection.execute(
        "SELECT name,sql FROM sqlite_master WHERE type='trigger'"
    ).fetchall()
    views = connection.execute(
        "SELECT name,sql FROM sqlite_master WHERE type='view'"
    ).fetchall()
    for name, _ in views:
        connection.execute('DROP VIEW "' + name.replace('"', '""') + '"')
    for name, _ in triggers:
        connection.execute('DROP TRIGGER "' + name.replace('"', '""') + '"')
    connection.execute(
        "CREATE TABLE countries(code TEXT PRIMARY KEY NOT NULL, "
        "name TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE cities(city_uid TEXT PRIMARY KEY NOT NULL, "
        "name TEXT NOT NULL, country_code TEXT NOT NULL "
        "REFERENCES countries(code), region TEXT)"
    )
    connection.executemany(
        "INSERT INTO countries VALUES (?,?)",
        [(country.code, country.name) for country in mapping.countries],
    )
    connection.executemany(
        "INSERT INTO cities VALUES (?,?,?,?)",
        [
            (c.city_uid, c.name, c.country.code, c.region)
            for c in mapping.cities
        ],
    )
    connection.execute("ALTER TABLE facilities ADD COLUMN city_uid TEXT")
    connection.executemany(
        "UPDATE facilities SET city_uid=? WHERE facility_uid=?",
        [(a.city_uid, a.facility_uid) for a in mapping.facilities],
    )
    rebuild_geographical_table(connection, "facilities")
    rebuild_geographical_table(connection, "companies")
    for _, sql in triggers:
        connection.execute(sql)
    for name, sql in views:
        if name == "facility_catalog_full":
            sql = (
                sql.replace("f.city,", "g.name AS city,")
                .replace("f.country_code,", "g.country_code,")
                .replace(
                    "FROM facilities AS f",
                    "FROM facilities AS f JOIN cities AS g "
                    "ON g.city_uid = f.city_uid",
                )
            )
        connection.execute(sql)
        connection.execute(
            'SELECT * FROM "' + name.replace('"', '""') + '" LIMIT 0'
        )
    connection.execute(
        "UPDATE metadata SET value='4.0.0' WHERE key='schema_version'"
    )
    connection.execute(
        "INSERT INTO metadata(key,value) "
        "VALUES('geography_mapping_version',?)",
        (str(mapping.version),),
    )


def rebuild_geographical_table(
    connection: sqlite3.Connection, table: str
) -> None:
    """Replace geography columns while retaining unrelated reference facts."""
    if table not in {"companies", "facilities"}:
        raise ValueError("Unsupported geography table.")
    schema = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name=? AND type='table'", (table,)
    ).fetchone()[0]
    indexes = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' "
        "AND tbl_name=? AND sql IS NOT NULL",
        (table,),
    ).fetchall()
    columns = [r[1] for r in connection.execute(f"PRAGMA table_info({table})")]
    schema = f"CREATE TABLE {table}_v4 " + schema[schema.index("(") :]
    if table == "facilities":
        for definition in (
            "city TEXT NOT NULL,",
            "state_region TEXT,",
            "country_code TEXT NOT NULL,",
        ):
            schema = schema.replace(definition, "")
        columns = [
            c
            for c in columns
            if c not in {"city", "state_region", "country_code"}
        ]
        schema = (
            schema.replace(
                "city_uid TEXT",
                "city_uid TEXT NOT NULL REFERENCES cities(city_uid)",
            )
            .replace(
                "latitude BETWEEN -90 AND 90 AND",
                "latitude IS NOT NULL AND longitude IS NOT NULL AND "
                "latitude BETWEEN -90 AND 90 AND",
            )
            .replace("facility_uid TEXT", "facility_uid TEXT NOT NULL")
        )
    else:
        schema = schema.replace(
            "country_code TEXT NOT NULL",
            "country_code TEXT NOT NULL REFERENCES countries(code)",
        ).replace("company_uid TEXT", "company_uid TEXT NOT NULL")
    connection.execute(schema)
    names = ",".join('"' + name + '"' for name in columns)
    connection.execute(
        f"INSERT INTO {table}_v4 ({names}) SELECT {names} FROM {table}"
    )
    connection.execute(f"DROP TABLE {table}")
    connection.execute(f"ALTER TABLE {table}_v4 RENAME TO {table}")
    for (sql,) in indexes:
        connection.execute(sql)


def validate_normalized_geography(
    connection: sqlite3.Connection,
    mapping: GeographyMapping,
    identities: tuple,
) -> None:
    """Reconcile identities and every assignment before publishing output."""
    metadata = dict(connection.execute("SELECT key,value FROM metadata"))
    expected_cities = {
        (c.city_uid, c.name, c.country.code, c.region) for c in mapping.cities
    }
    if (
        metadata.get("schema_version") != "4.0.0"
        or metadata.get("data_version") != mapping.source_data_version
        or metadata.get("geography_mapping_version") != str(mapping.version)
        or catalogue_identities(connection) != identities
        or set(connection.execute("SELECT * FROM cities")) != expected_cities
        or set(connection.execute("SELECT * FROM countries"))
        != {(c.code, c.name) for c in mapping.countries}
        or set(
            connection.execute("SELECT facility_uid,city_uid FROM facilities")
        )
        != {(a.facility_uid, a.city_uid) for a in mapping.facilities}
    ):
        raise ValueError("Normalized catalogue differs from reviewed mapping.")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Normalized catalogue has broken references.")
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Normalized catalogue integrity check failed.")
