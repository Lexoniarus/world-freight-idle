"""SQLite persistence for global derived routing anchors."""

from __future__ import annotations

import json
from typing import Any

from app.domain.geography import Coordinates
from app.domain.routing_anchors import RoutingAnchor, RoutingAnchorStatus
from app.repositories.game_database import SqliteGameDatabase

SCHEMA = """
CREATE TABLE IF NOT EXISTS routing_anchors (
    facility_uid TEXT NOT NULL,
    routing_profile TEXT NOT NULL,
    anchor_lat REAL,
    anchor_lon REAL,
    method TEXT NOT NULL,
    facility_lat REAL,
    facility_lon REAL,
    snap_distance_m REAL,
    validation_status TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_revision TEXT,
    validated_at REAL NOT NULL,
    PRIMARY KEY (facility_uid, routing_profile),
    CHECK (
        (validation_status = 'validated'
            AND anchor_lat IS NOT NULL AND anchor_lon IS NOT NULL)
        OR
        (validation_status <> 'validated'
            AND anchor_lat IS NULL AND anchor_lon IS NULL)
    )
);
CREATE TABLE IF NOT EXISTS routing_anchor_sources (
    facility_uid TEXT NOT NULL, routing_profile TEXT NOT NULL,
    fingerprint TEXT, PRIMARY KEY (facility_uid, routing_profile)
);
"""

_STATUS_VALUES: dict[str, RoutingAnchorStatus] = {
    "validated": "validated",
    "no_truck_edge": "no_truck_edge",
    "snap_too_far": "snap_too_far",
    "geocoding_failed": "geocoding_failed",
    "provider_unavailable": "provider_unavailable",
    "invalid_response": "invalid_response",
}


class SqliteRoutingAnchorRepository:
    """Persist derived anchors outside immutable catalogues."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        self._database = database
        with self._database.connect() as connection:
            connection.executescript(SCHEMA)

    def get(
        self,
        facility_uid: str,
        routing_profile: str,
    ) -> RoutingAnchor | None:
        """Return one persisted routing result."""
        return self.get_many((facility_uid,), routing_profile).get(
            facility_uid
        )

    def get_many(
        self,
        facility_uids: tuple[str, ...],
        routing_profile: str,
    ) -> dict[str, RoutingAnchor | None]:
        """Read anchors and their fingerprints with one set query."""
        result: dict[str, RoutingAnchor | None] = {
            uid: None for uid in facility_uids
        }
        if not facility_uids:
            return result
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT a.facility_uid, a.routing_profile, a.anchor_lat, "
                "a.anchor_lon, a.method, a.facility_lat, a.facility_lon, "
                "a.snap_distance_m, a.validation_status, a.provider, "
                "a.provider_revision, a.validated_at, s.fingerprint "
                "FROM routing_anchors a LEFT JOIN routing_anchor_sources s "
                "ON s.facility_uid=a.facility_uid AND "
                "s.routing_profile=a.routing_profile "
                "WHERE a.facility_uid IN "
                "(SELECT value FROM json_each(?)) "
                "AND a.routing_profile=?",
                (json.dumps(facility_uids), routing_profile),
            ).fetchall()
        for row in rows:
            result[str(row[0])] = self._decode(row)
        return result

    @staticmethod
    def _decode(row: Any) -> RoutingAnchor:
        """Decode one joined adapter row into a routing anchor."""
        anchor = (
            Coordinates(float(row[2]), float(row[3]))
            if row[2] is not None and row[3] is not None
            else None
        )
        facility_coordinates = (
            Coordinates(float(row[5]), float(row[6]))
            if row[5] is not None and row[6] is not None
            else None
        )
        try:
            validation_status = _STATUS_VALUES[str(row[8])]
        except KeyError as exc:
            raise ValueError(
                "Invalid persisted routing-anchor status."
            ) from exc
        return RoutingAnchor(
            facility_uid=str(row[0]),
            routing_profile=str(row[1]),
            anchor=anchor,
            method=str(row[4]),
            facility_coordinates=facility_coordinates,
            snap_distance_m=(float(row[7]) if row[7] is not None else None),
            validation_status=validation_status,
            provider=str(row[9]),
            provider_revision=(str(row[10]) if row[10] is not None else None),
            validated_at=float(row[11]),
            source_fingerprint=row[12],
        )

    def put(self, anchor: RoutingAnchor) -> None:
        """Replace one routing result after provider awaits have completed."""
        anchor_lat = anchor.anchor.latitude if anchor.anchor else None
        anchor_lon = anchor.anchor.longitude if anchor.anchor else None
        facility_lat = (
            anchor.facility_coordinates.latitude
            if anchor.facility_coordinates
            else None
        )
        facility_lon = (
            anchor.facility_coordinates.longitude
            if anchor.facility_coordinates
            else None
        )
        with (
            self._database.transaction(),
            self._database.connect() as connection,
        ):
            connection.execute(
                """
                INSERT INTO routing_anchors (
                    facility_uid, routing_profile, anchor_lat, anchor_lon,
                    method, facility_lat, facility_lon, snap_distance_m,
                    validation_status, provider, provider_revision,
                    validated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(facility_uid, routing_profile) DO UPDATE SET
                    anchor_lat=excluded.anchor_lat,
                    anchor_lon=excluded.anchor_lon,
                    method=excluded.method,
                    facility_lat=excluded.facility_lat,
                    facility_lon=excluded.facility_lon,
                    snap_distance_m=excluded.snap_distance_m,
                    validation_status=excluded.validation_status,
                    provider=excluded.provider,
                    provider_revision=excluded.provider_revision,
                    validated_at=excluded.validated_at
                """,
                (
                    anchor.facility_uid,
                    anchor.routing_profile,
                    anchor_lat,
                    anchor_lon,
                    anchor.method,
                    facility_lat,
                    facility_lon,
                    anchor.snap_distance_m,
                    anchor.validation_status,
                    anchor.provider,
                    anchor.provider_revision,
                    anchor.validated_at,
                ),
            )
            connection.execute(
                "INSERT INTO routing_anchor_sources VALUES (?, ?, ?) "
                "ON CONFLICT(facility_uid, routing_profile) DO UPDATE "
                "SET fingerprint=excluded.fingerprint",
                (
                    anchor.facility_uid,
                    anchor.routing_profile,
                    anchor.source_fingerprint,
                ),
            )

    def put_leased(
        self, anchor: RoutingAnchor, owner: str, now: float
    ) -> bool:
        """Fence anchor publication with its infrastructure lease."""
        subject = f"anchor:{anchor.facility_uid}:{anchor.routing_profile}"
        with self._database.transaction(), self._database.connect() as conn:
            lease = conn.execute(
                "SELECT 1 FROM routing_leases "
                "WHERE subject=? AND owner=? AND expires_at>?",
                (subject, owner, now),
            ).fetchone()
            if lease is None:
                return False
            self.put(anchor)
            return True
