"""SQLite provider cache independent of player-state serialization."""

import json
import logging
import time
from typing import Any

from app.domain.errors import PersistenceError
from app.repositories.game_database import SqliteGameDatabase

SCHEMA = """
CREATE TABLE IF NOT EXISTS geocode_cache (
    address TEXT PRIMARY KEY,
    lat REAL NOT NULL, lon REAL NOT NULL,
    display_name TEXT NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS route_cache (
    cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at REAL NOT NULL
);
"""
LOGGER = logging.getLogger(__name__)


class SqliteProviderCache:
    """Persist external provider documents without game-state KV access."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        self._database = database
        with database.connect() as connection:
            connection.executescript(SCHEMA)

    def get_route(self, cache_key: str) -> dict[str, Any] | None:
        """Return a stored document for validation by the provider adapter."""
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM route_cache WHERE cache_key=?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except ValueError:
            LOGGER.warning(
                "Invalid route cache document ignored",
                extra={"event": "cache.invalid_route"},
            )
            return None

    def put_route(self, cache_key: str, payload: dict[str, Any]) -> None:
        """Replace one validated route response."""
        try:
            encoded = json.dumps(payload, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise PersistenceError("Ungültiger Cacheinhalt.") from exc
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO route_cache VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                payload=excluded.payload, updated_at=excluded.updated_at""",
                (cache_key, encoded, time.time()),
            )

    def get_geocode(self, address: str) -> dict[str, Any] | None:
        """Read cached offline enrichment metadata."""
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM geocode_cache WHERE address=?",
                (address,),
            ).fetchone()
        return dict(row) if row is not None else None

    def put_geocode(
        self, address: str, lat: float, lon: float, display_name: str
    ) -> None:
        """Replace one enrichment result with its observation time."""
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO geocode_cache VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET lat=excluded.lat,
                lon=excluded.lon, display_name=excluded.display_name,
                updated_at=excluded.updated_at""",
                (address, lat, lon, display_name, time.time()),
            )
