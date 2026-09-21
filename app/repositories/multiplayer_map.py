"""Read-only cross-player projection for the shared world map."""

from __future__ import annotations

import json
from typing import Any

from app.repositories.sqlite_store import SqliteStore


class MultiplayerMapRepository:
    """Read only the persisted fields required by shared live traffic."""

    def __init__(self, store: SqliteStore) -> None:
        self.store = store

    def list_active_transports(self, active_at: float) -> list[dict[str, Any]]:
        """Project only the public fields required for live traffic."""
        with self.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    u.id AS user_id,
                    u.username AS username,
                    json_extract(trip.value, '$.id') AS trip_id,
                    json_extract(trip.value, '$.vehicle_id') AS vehicle_id,
                    COALESCE(
                        json_extract(vehicle.value, '$.model_id'),
                        ''
                    ) AS model_id,
                    json_extract(
                        vehicle.value,
                        '$.name'
                    ) AS model_name,
                    json_extract(
                        trip.value,
                        '$.departed_at'
                    ) AS departed_at,
                    json_extract(
                        trip.value,
                        '$.arrives_at'
                    ) AS arrives_at,
                    json_extract(
                        trip.value,
                        '$.route_geojson'
                    ) AS route_geojson
                FROM users AS u
                JOIN kv AS trip_state
                    ON trip_state.key =
                        'user:' || u.id || ':active_trips'
                JOIN json_each(trip_state.value) AS trip
                JOIN kv AS vehicle_state
                    ON vehicle_state.key =
                        'user:' || u.id || ':vehicles'
                JOIN json_each(vehicle_state.value) AS vehicle
                    ON json_extract(vehicle.value, '$.id') =
                        json_extract(trip.value, '$.vehicle_id')
                WHERE
                    json_type(trip.value, '$.id') = 'text'
                    AND json_type(trip.value, '$.vehicle_id') = 'text'
                    AND json_type(
                        trip.value,
                        '$.departed_at'
                    ) IN ('integer', 'real')
                    AND json_type(
                        trip.value,
                        '$.arrives_at'
                    ) IN ('integer', 'real')
                    AND json_extract(
                        trip.value,
                        '$.arrives_at'
                    ) > ?
                    AND json_type(
                        trip.value,
                        '$.route_geojson'
                    ) = 'object'
                ORDER BY
                    departed_at ASC,
                    trip_id ASC
                """,
                (active_at,),
            ).fetchall()
        return [
            {
                "user_id": row["user_id"],
                "username": row["username"],
                "id": row["trip_id"],
                "vehicle_id": row["vehicle_id"],
                "model_id": row["model_id"],
                "model_name": row["model_name"] or row["model_id"],
                "departed_at": row["departed_at"],
                "arrives_at": row["arrives_at"],
                "route_geojson": json.loads(row["route_geojson"]),
            }
            for row in rows
        ]
