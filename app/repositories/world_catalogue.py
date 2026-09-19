"""Read-only SQLite boundary for real companies and public facilities."""

import logging
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from app.domain.errors import WorldCatalogueError
from app.domain.world import (
    Company,
    DocumentedCargo,
    DocumentedGood,
    Facility,
    SourceReference,
    WorldSnapshot,
)

LOGGER = logging.getLogger(__name__)


class SqliteWorldCatalogue:
    """Read a consistent catalogue transaction and release every connection."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> WorldSnapshot:
        """Reject incompatible references; never create a missing database."""
        try:
            with closing(
                sqlite3.connect(
                    self.path.resolve().as_uri() + "?mode=ro",
                    uri=True,
                )
            ) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA query_only=ON")
                connection.execute("BEGIN")
                return read_world_snapshot(connection)
        except (
            sqlite3.Error,
            ValueError,
            TypeError,
            KeyError,
            OSError,
        ) as exc:
            LOGGER.error(
                "World catalogue unavailable",
                extra={
                    "event": "world.catalogue_error",
                    "data": {"error": str(exc)},
                },
            )
            raise WorldCatalogueError(
                "Weltkatalog derzeit nicht verfügbar."
            ) from exc


def validate_world_schema(connection: sqlite3.Connection) -> str:
    """Validate schema and references including polymorphic identifiers."""
    metadata = dict(connection.execute("SELECT key,value FROM metadata"))
    if metadata.get("schema_version") != "3.0.0":
        raise ValueError("Unsupported world schema")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Broken world references")
    if connection.execute("""
        SELECT 1 FROM external_identifiers e
        WHERE (entity_type='company' AND NOT EXISTS (
            SELECT 1 FROM companies c WHERE c.company_id=e.entity_id))
        OR (entity_type='facility' AND NOT EXISTS (
            SELECT 1 FROM facilities f WHERE f.facility_id=e.entity_id))
    """).fetchone():
        raise ValueError("Orphan external identifier")
    if connection.execute(
        "SELECT 1 FROM facilities "
        "WHERE (latitude IS NULL) != (longitude IS NULL)"
    ).fetchone():
        raise ValueError("Incomplete coordinate pair")
    return metadata["data_version"]


def validate_uid(value: str) -> str:
    """Public identities are canonical UUIDs, never row numbers or names."""
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError("Invalid world UID")
    return value


def source_reference(row: sqlite3.Row) -> SourceReference:
    """Project only explicit nonempty source URLs into public provenance."""
    url = row["source_url"]
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        raise ValueError("Missing world provenance")
    return SourceReference(url, row["source_role"], row["verified_at"])


def read_companies(connection: sqlite3.Connection) -> dict[int, Company]:
    """Resolve internal foreign keys into immutable company projections."""
    sources: dict[int, list[SourceReference]] = {}
    for row in connection.execute("SELECT * FROM company_sources"):
        sources.setdefault(row["company_id"], []).append(source_reference(row))
    return {
        row["company_id"]: Company(
            validate_uid(row["company_uid"]),
            row["legal_name"],
            row["display_name"],
            row["country_code"],
            row["website_url"],
            tuple(sources.get(row["company_id"], [])),
        )
        for row in connection.execute(
            "SELECT * FROM companies ORDER BY company_uid"
        )
    }


def read_cargo(
    connection: sqlite3.Connection,
) -> dict[int, list[DocumentedCargo]]:
    """Read documented profiles without inventing goods or input demand."""
    result: dict[int, list[DocumentedCargo]] = {}
    for row in connection.execute("""
        SELECT p.*, c.nst_code, c.name, c.requires_cooling, c.hazardous,
               c.bulk,c.liquid,s.base_url,s.retrieved_at
        FROM facility_cargo_profiles p JOIN cargo_types c USING(cargo_type_id)
        JOIN sources s USING(source_id)
    """):
        standard = not any(
            row[key]
            for key in (
                "requires_cooling",
                "hazardous",
                "bulk",
                "liquid",
            )
        )
        source = SourceReference(
            row["base_url"],
            row["evidence_type"],
            row["retrieved_at"],
        )
        if not source.url or not source.url.startswith(
            ("http://", "https://")
        ):
            raise ValueError("Missing cargo provenance")
        item = DocumentedCargo(
            row["nst_code"],
            row["name"],
            row["cargo_role"],
            standard,
            row["evidence_type"],
            source,
        )
        result.setdefault(row["facility_id"], []).append(item)
    return result


def read_facility(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    companies: dict[int, Company],
    cargo: tuple[DocumentedCargo, ...],
    version: str,
) -> Facility:
    """Join all endpoint facts into a self-contained immutable reference."""
    uid = validate_uid(row["facility_uid"])
    sources = tuple(
        source_reference(s)
        for s in connection.execute(
            "SELECT * FROM facility_sources WHERE facility_id=?",
            (row["facility_id"],),
        )
    )
    if not sources:
        raise ValueError("Facility without provenance")
    evidence = []
    for entry in connection.execute(
        "SELECT * FROM facility_geocoding_evidence WHERE facility_id=?",
        (row["facility_id"],),
    ):
        if (
            entry["latitude"] == row["latitude"]
            and entry["longitude"] == row["longitude"]
            and entry["precision_type"]
            in {
                "official_facility_coordinate",
                "facility_centroid",
                "osm_feature",
                "verified_address_point",
            }
            and isinstance(entry["source_url"], str)
            and entry["source_url"].startswith(("https://", "http://"))
            and entry["verified_at"]
        ):
            evidence.append(
                SourceReference(
                    entry["source_url"],
                    "coordinates",
                    entry["verified_at"],
                    entry["precision_type"],
                    entry["provider"],
                )
            )
    aliases = tuple(
        r[0]
        for r in connection.execute(
            "SELECT alias FROM facility_aliases WHERE facility_uid=?",
            (uid,),
        )
    )
    address = ", ".join(
        str(row[key])
        for key in (
            "street",
            "house_number",
            "postcode",
            "city",
            "country_code",
        )
        if row[key]
    )
    return Facility(
        uid,
        companies.get(row["company_id"]),
        row["name"],
        row["type_code"],
        row["city"],
        row["country_code"],
        address,
        row["latitude"],
        row["longitude"],
        row["geocoding_status"],
        sources,
        tuple(evidence),
        cargo,
        version,
        aliases,
        read_handled_goods(connection, row["facility_id"]),
    )


def read_handled_goods(
    connection: sqlite3.Connection,
    facility_id: int,
) -> tuple[DocumentedGood, ...]:
    """Keep exact documented goods separate from simulated contract cargo."""
    return tuple(
        DocumentedGood(
            row["goods_description"], row["nst_code"], source_reference(row)
        )
        for row in connection.execute(
            """SELECT g.goods_description,c.nst_code,
                s.base_url AS source_url,g.evidence_type AS source_role,
                s.retrieved_at AS verified_at
            FROM facility_handled_goods g
            LEFT JOIN cargo_types c USING(cargo_type_id)
            JOIN sources s USING(source_id) WHERE g.facility_id=?
            ORDER BY g.handled_goods_id""",
            (facility_id,),
        )
    )


def read_world_snapshot(connection: sqlite3.Connection) -> WorldSnapshot:
    """Read one complete revision and report the routability boundary."""
    version = validate_world_schema(connection)
    companies = read_companies(connection)
    cargo = read_cargo(connection)
    facilities = tuple(
        read_facility(
            connection,
            row,
            companies,
            tuple(cargo.get(row["facility_id"], [])),
            version,
        )
        for row in connection.execute("""
        SELECT f.*,t.code AS type_code FROM facilities f
        JOIN facility_types t USING(facility_type_id) ORDER BY facility_uid
    """)
    )
    if not facilities:
        raise ValueError("Empty world catalogue")
    for values in (companies.values(), facilities):
        identities = [
            getattr(v, "facility_uid", None) or getattr(v, "company_uid")
            for v in values
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate world UID")
    excluded = sum(not f.is_routable() for f in facilities)
    LOGGER.info(
        "World catalogue read",
        extra={
            "event": "world.catalogue_read",
            "data": {
                "catalogue_version": version,
                "facilities": len(facilities),
                "excluded": excluded,
                "exclusion_reason": "missing_or_invalid_coordinate_evidence",
            },
        },
    )
    return WorldSnapshot(version, tuple(companies.values()), facilities)
