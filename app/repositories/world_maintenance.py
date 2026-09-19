"""Explicit offline schema maintenance; never used by HTTP requests."""

import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

from app.repositories.world_catalogue import read_world_snapshot


class WorldMaintenanceRepository:
    """Atomically upgrade a backed-up reference catalogue in place."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def upgrade(self, entries: list[dict[str, Any]]) -> None:
        """Preserve existing identities and roll back every failed edit."""
        with closing(
            sqlite3.connect(
                self.path.resolve().as_uri() + "?mode=rw",
                uri=True,
            )
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                version = dict(
                    connection.execute("SELECT key,value FROM metadata")
                ).get("schema_version")
                if version == "2.0.0":
                    add_world_identities(connection)
                elif version != "3.0.0":
                    raise ValueError("Unsupported source world schema")
                for entry in entries:
                    insert_legacy_facility(connection, entry)
                connection.execute(
                    "UPDATE metadata SET value='3.0.0' "
                    "WHERE key='schema_version'"
                )
                world = read_world_snapshot(connection)
                for entry in entries:
                    facility = world.get_facility(entry["alias"])
                    if (
                        not facility.is_routable()
                        or not facility.outbound_cargo()
                    ):
                        raise ValueError("Legacy endpoint is not market ready")


def add_world_identities(connection: sqlite3.Connection) -> None:
    """Allocate opaque identities once and enforce mandatory unique values."""
    for table, kind in (("companies", "company"), ("facilities", "facility")):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {kind}_uid TEXT")
        identifiers = connection.execute(
            f"SELECT {kind}_id FROM {table}"
        ).fetchall()
        for row in identifiers:
            connection.execute(
                f"UPDATE {table} SET {kind}_uid=? WHERE {kind}_id=?",
                (str(uuid.uuid4()), row[0]),
            )
        connection.execute(
            f"CREATE UNIQUE INDEX uq_{kind}_uid ON {table}({kind}_uid)"
        )
        for operation in ("INSERT", "UPDATE"):
            connection.execute(f"""
                CREATE TRIGGER require_{kind}_uid_{operation.lower()}
                BEFORE {operation} ON {table}
                WHEN NEW.{kind}_uid IS NULL OR length(NEW.{kind}_uid)!=36
                BEGIN SELECT RAISE(ABORT,'Missing world UID'); END
            """)
        connection.execute(f"""
            CREATE TRIGGER preserve_{kind}_uid BEFORE UPDATE ON {table}
            WHEN NEW.{kind}_uid != OLD.{kind}_uid
            BEGIN SELECT RAISE(ABORT,'World UID is immutable'); END
        """)
    connection.execute("""
        CREATE TABLE facility_aliases(
            alias TEXT PRIMARY KEY,
            facility_uid TEXT NOT NULL REFERENCES facilities(facility_uid)
        )
    """)
    for operation in ("INSERT", "UPDATE"):
        connection.execute(f"""
            CREATE TRIGGER coordinate_pair_{operation.lower()}
            BEFORE {operation} ON facilities
            WHEN (NEW.latitude IS NULL) != (NEW.longitude IS NULL)
            BEGIN SELECT RAISE(ABORT,'Incomplete coordinate pair'); END
        """)


def insert_world_source(
    connection: sqlite3.Connection,
    url: str,
    name: str,
    source_type: str,
    date: str,
) -> int:
    """Insert provenance for one independently reviewed fact."""
    cursor = connection.execute(
        """
        INSERT INTO sources(source_type,name,base_url,retrieved_at,notes)
        VALUES(?,?,?,?,?)
    """,
        (source_type, name, url, date, "Reviewed legacy endpoint evidence"),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def insert_legacy_facility(
    connection: sqlite3.Connection,
    entry: dict[str, Any],
) -> None:
    """Add a curated real endpoint once, retaining all later UUIDs."""
    if connection.execute(
        "SELECT 1 FROM facility_aliases WHERE alias=?",
        (entry["alias"],),
    ).fetchone():
        return
    official = insert_world_source(
        connection,
        entry["source_url"],
        entry["name"],
        "official",
        entry["verified_at"],
    )
    geo_source = insert_world_source(
        connection,
        entry["coordinate_url"],
        entry["provider"],
        "coordinate_evidence",
        entry["verified_at"],
    )
    company = insert_reference_company(connection, entry, official)
    facility, uid = insert_reference_facility(connection, entry, company)
    connection.execute(
        "INSERT INTO facility_aliases VALUES(?,?)", (entry["alias"], uid)
    )
    insert_facility_evidence(connection, entry, facility, official, geo_source)
    insert_documented_goods(connection, entry, facility, official)


def insert_reference_company(
    connection: sqlite3.Connection,
    entry: dict[str, Any],
    official: int,
) -> int:
    """Persist a reviewed reference company and its identity source."""
    company = connection.execute(
        """
        INSERT INTO companies(legal_name,display_name,country_code,
            website_url,verification_status,created_at,updated_at,company_uid)
        VALUES(?,?,?,?,?,?,?,?)
    """,
        (
            entry["company"],
            entry["company"],
            entry["country"],
            entry["source_url"],
            "official_verified",
            entry["verified_at"],
            entry["verified_at"],
            str(uuid.uuid4()),
        ),
    ).lastrowid
    connection.execute(
        """
        INSERT INTO company_sources VALUES(?,?,?,?,?)
    """,
        (
            company,
            official,
            entry["source_url"],
            "identity",
            entry["verified_at"],
        ),
    )
    assert company is not None
    return company


def insert_reference_facility(
    connection: sqlite3.Connection,
    entry: dict[str, Any],
    company: int,
) -> tuple[int, str]:
    """Persist a reviewed endpoint with its newly allocated durable UID."""
    uid = str(uuid.uuid4())
    facility = connection.execute(
        """
        INSERT INTO facilities(company_id,facility_type_id,name,street,
            house_number,postcode,city,country_code,latitude,longitude,
            osm_type,osm_id,website_url,verification_status,created_at,
            updated_at,geocoding_status,facility_uid)
        VALUES(?,(SELECT facility_type_id FROM facility_types
                  WHERE code='intermodal_terminal'),
                  ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,
        (
            company,
            entry["name"],
            entry["street"],
            entry["house_number"],
            entry["postcode"],
            entry["city"],
            entry["country"],
            entry["lat"],
            entry["lon"],
            entry["osm_type"],
            entry["osm_id"],
            entry["source_url"],
            "official_verified",
            entry["verified_at"],
            entry["verified_at"],
            "verified_coordinates",
            uid,
        ),
    ).lastrowid
    assert facility is not None
    return facility, uid


def insert_facility_evidence(
    connection: sqlite3.Connection,
    entry: dict[str, Any],
    facility: int,
    official: int,
    geo_source: int,
) -> None:
    """Attach independently reviewed address and coordinate provenance."""
    connection.execute(
        "INSERT INTO facility_sources VALUES(?,?,?,?,?)",
        (
            facility,
            official,
            entry["source_url"],
            "address_and_activity",
            entry["verified_at"],
        ),
    )
    connection.execute(
        """
        INSERT INTO facility_geocoding_evidence(facility_id,latitude,longitude,
            precision_type,provider,source_id,source_url,verified_at,
            osm_type,osm_id)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """,
        (
            facility,
            entry["lat"],
            entry["lon"],
            entry["precision"],
            entry["provider"],
            geo_source,
            entry["coordinate_url"],
            entry["verified_at"],
            entry["osm_type"],
            entry["osm_id"],
        ),
    )


def insert_documented_goods(
    connection: sqlite3.Connection,
    entry: dict[str, Any],
    facility: int,
    official: int,
) -> None:
    """Attach documented handling activity, without simulated demand."""
    cargo = connection.execute(
        "SELECT cargo_type_id FROM cargo_types WHERE nst_code=?",
        (entry["cargo_code"],),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO facility_cargo_profiles(
            facility_id,cargo_type_id,cargo_role,
            priority_score,volume_band,confidence,source_id,evidence_type,
            notes)
        VALUES(?,?,'both',1,'high',1,?,'official',?)
    """,
        (facility, cargo, official, entry["goods"]),
    )
    connection.execute(
        """
        INSERT INTO facility_handled_goods(facility_id,goods_description,
            cargo_type_id,evidence_type,source_id) VALUES(?,?,?,'official',?)
    """,
        (facility, entry["goods"], cargo, official),
    )
