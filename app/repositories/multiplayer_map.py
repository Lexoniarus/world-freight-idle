"""Read-only cross-player state projection for the shared world map."""

from __future__ import annotations

import json

from app.repositories.sqlite_store import SqliteStore


class MultiplayerMapRepository:
    """Read the minimum shared state needed for multiplayer map traffic."""

    def __init__(self, store: SqliteStore) -> None:
        self.store = store

    def list_player_states(self) -> list[dict]:
        """Return usernames plus persisted vehicle and trip snapshots."""
        with self.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    u.id AS user_id,
                    u.username AS username,
                    trips.value AS active_trips,
                    vehicles.value AS vehicles
                FROM users u
                LEFT JOIN kv trips
                    ON trips.key = 'user:' || u.id || ':active_trips'
                LEFT JOIN kv vehicles
                    ON vehicles.key = 'user:' || u.id || ':vehicles'
                ORDER BY u.created_at ASC, u.id ASC
                """
            ).fetchall()
        return [
            {
                "user_id": row["user_id"],
                "username": row["username"],
                "active_trips": json.loads(row["active_trips"] or "[]"),
                "vehicles": json.loads(row["vehicles"] or "[]"),
            }
            for row in rows
        ]
