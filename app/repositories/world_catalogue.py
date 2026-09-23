"""Read-only SQLite boundary for real companies and public facilities."""

import logging
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from app.domain.cargo import FacilityNhmProfile, NhmProduct
from app.domain.errors import WorldCatalogueError
from app.domain.evidence import SourceReference
from app.domain.world import Company, DocumentedGood, Facility, WorldSnapshot

LOGGER = logging.getLogger(__name__)

_REQUIRED_WORLD_TABLES = {
    "facilities",
    "facility_nhm_profiles",
    "nhm_codes",
}
_REQUIRED_PROFILE_SYSTEM = "NHM 2026 via facility_nhm_profiles -> nhm_codes"


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
    """Validate the NHM-capable schema and cross-table invariants."""
    metadata = dict(connection.execute("SELECT key,value FROM metadata"))
    if metadata.get("schema_version") != "3.0.0":
        raise ValueError("Unsupported world schema")
    if metadata.get("operational_profile_system") != _REQUIRED_PROFILE_SYSTEM:
        raise ValueError("Missing NHM profile capability")

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if not _REQUIRED_WORLD_TABLES.issubset(tables):
        raise ValueError("Missing NHM world tables")
    if connection.execute("""
        SELECT 1
        FROM company_sources cs
        JOIN sources s USING(source_id)
        WHERE s.base_url IS NULL
           OR (
               s.base_url NOT LIKE 'http://%'
               AND s.base_url NOT LIKE 'https://%'
           )
        LIMIT 1
    """).fetchone():
        raise ValueError("Missing world provenance")
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
    if connection.execute(
        "SELECT 1 FROM cargo_types WHERE nst_code LIKE 'NHM:%' LIMIT 1"
    ).fetchone():
        raise ValueError("NHM pseudo code stored in NST catalogue")
    if connection.execute("""
        SELECT 1
        FROM facility_nhm_profiles p
        JOIN nhm_codes n USING(nhm_row_id)
        WHERE n.code IS NULL OR n.is_numeric != 1
        LIMIT 1
    """).fetchone():
        raise ValueError("Invalid operative NHM profile")
    if connection.execute("""
        SELECT 1
        FROM facilities f
        LEFT JOIN facility_nhm_profiles p USING(facility_id)
        GROUP BY f.facility_id
        HAVING SUM(
            CASE WHEN p.cargo_role IN ('input','both') THEN 1 ELSE 0 END
        ) = 0
        OR SUM(
            CASE WHEN p.cargo_role IN ('output','both') THEN 1 ELSE 0 END
        ) = 0
        LIMIT 1
    """).fetchone():
        raise ValueError("Facility without complete NHM behavior")
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


def read_nhm_ancestors(
    connection: sqlite3.Connection,
) -> dict[int, tuple[int, ...]]:
    """Build complete self-to-root NHM ancestry from stored parent links."""
    parent_by_row = {
        int(row["nhm_row_id"]): (
            int(row["parent_row_id"])
            if row["parent_row_id"] is not None
            else None
        )
        for row in connection.execute(
            "SELECT nhm_row_id,parent_row_id FROM nhm_codes"
        )
    }
    ancestors: dict[int, tuple[int, ...]] = {}
    for row_id in parent_by_row:
        chain: list[int] = []
        seen: set[int] = set()
        current: int | None = row_id
        while current is not None:
            if current in seen:
                raise ValueError("Cyclic NHM hierarchy")
            if current not in parent_by_row:
                raise ValueError("Broken NHM parent reference")
            seen.add(current)
            chain.append(current)
            current = parent_by_row[current]
        ancestors[row_id] = tuple(chain)
    return ancestors


def read_cargo(
    connection: sqlite3.Connection,
) -> dict[int, list[FacilityNhmProfile]]:
    """Read operative NHM facility profiles and preserve evidence quality."""
    ancestors = read_nhm_ancestors(connection)
    result: dict[int, list[FacilityNhmProfile]] = {}
    products: dict[int, NhmProduct] = {}
    rows = connection.execute("""
        SELECT
            p.facility_id,
            p.nhm_row_id,
            p.cargo_role,
            p.priority_score,
            p.confidence,
            p.evidence_type,
            n.code,
            COALESCE(
                NULLIF(n.label_de,''),
                NULLIF(n.name_de,''),
                NULLIF(n.label_en,''),
                NULLIF(n.name_en,''),
                n.code
            ) AS cargo_name,
            s.base_url,
            s.retrieved_at
        FROM facility_nhm_profiles p
        JOIN nhm_codes n USING(nhm_row_id)
        LEFT JOIN sources s USING(source_id)
        ORDER BY p.facility_id, p.profile_id
    """)
    for row in rows:
        base_url = row["base_url"]
        source = None
        if isinstance(base_url, str) and base_url.startswith(
            ("http://", "https://")
        ):
            source = SourceReference(
                base_url,
                row["evidence_type"],
                row["retrieved_at"],
            )
        elif row["evidence_type"] != "derived":
            raise ValueError("Missing cargo provenance")
        row_id = int(row["nhm_row_id"])
        if row_id not in products:
            products[row_id] = NhmProduct(
                row_id, row["code"], row["cargo_name"], ancestors[row_id]
            )
        profile = FacilityNhmProfile(
            products[row_id],
            row["cargo_role"],
            row["evidence_type"],
            float(row["confidence"]),
            float(row["priority_score"]),
            source,
        )
        result.setdefault(int(row["facility_id"]), []).append(profile)
    return result


def read_facility(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    companies: dict[int, Company],
    cargo: tuple[FacilityNhmProfile, ...],
    version: str,
) -> Facility:
    """Join all endpoint facts into a self-contained immutable reference."""
    uid = validate_uid(row["facility_uid"])
    sources = tuple(
        source_reference(source)
        for source in connection.execute(
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
            and (
                entry["source_url"].startswith(("https://", "http://"))
                or (
                    row["geocoding_status"] == "estimated_for_simulation"
                    and entry["source_url"].startswith(
                        "internal://simulation-"
                    )
                )
            )
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
        alias[0]
        for alias in connection.execute(
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
    """Keep exact documented goods separate from simulated behavior."""
    return tuple(
        DocumentedGood(
            row["goods_description"],
            row["nst_code"],
            source_reference(row),
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
            getattr(value, "facility_uid", None)
            or getattr(value, "company_uid")
            for value in values
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate world UID")
    routable = sum(facility.is_routable() for facility in facilities)
    verified = sum(facility.has_verified_location() for facility in facilities)
    LOGGER.info(
        "World catalogue read",
        extra={
            "event": "world.catalogue_read",
            "data": {
                "catalogue_version": version,
                "facilities": len(facilities),
                "routable": routable,
                "verified_locations": verified,
                "estimated_locations": routable - verified,
                "excluded": len(facilities) - routable,
            },
        },
    )
    return WorldSnapshot(version, tuple(companies.values()), facilities)
