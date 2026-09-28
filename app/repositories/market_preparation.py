"""Durable preparation scheduling in the existing game database."""

import json
import uuid
from dataclasses import asdict

from app.domain.market import VehicleCoverageDiagnostic
from app.domain.market_preparation import PreparationStatus
from app.repositories.game_database import SqliteGameDatabase


class SqlitePreparationStore:
    """Persist player demand without owning provider work or its leases."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Initialize additive infrastructure before opening game work."""
        self.database = database
        with database.connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS market_preparations ("
                "user_id TEXT PRIMARY KEY REFERENCES player_states(user_id) "
                "ON DELETE CASCADE, preparation_id TEXT NOT NULL, "
                "generation TEXT NOT NULL, status TEXT NOT NULL, "
                "next_retry_at REAL, updated_at REAL NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS market_coverage ("
                "user_id TEXT PRIMARY KEY REFERENCES player_states(user_id) "
                "ON DELETE CASCADE, generation TEXT NOT NULL, "
                "payload TEXT NOT NULL)"
            )

    def ensure(self, user_id: str, now: float) -> None:
        """Coalesce reads while making expired or absent demand runnable."""
        status = self.status(user_id)
        if status is None:
            with self.database.transaction():
                if self.status(user_id) is None:
                    self.invalidate(user_id, now)
        elif status.status != "partial" and (
            status.next_retry_at is None or status.next_retry_at <= now
        ):
            with self.database.connect() as conn:
                conn.execute(
                    "UPDATE market_preparations SET status='partial' "
                    "WHERE user_id=? AND generation=?",
                    (user_id, status.generation),
                )

    def invalidate(self, user_id: str, now: float) -> None:
        """Fence a changed player's inputs using a new durable revision."""
        self.request(user_id, uuid.uuid4().hex, now)

    def diagnostics(
        self, user_id: str
    ) -> tuple[VehicleCoverageDiagnostic, ...]:
        """Read the last worker publication without scanning candidates."""
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM market_coverage WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return (
            tuple(
                VehicleCoverageDiagnostic(
                    item["vehicle_id"],
                    item["city_uid"],
                    item["offer_count"],
                    tuple(item["distance_counts"]),
                    tuple(item["unmet_bands"]),
                    tuple(item["unmet_facilities"]),
                )
                for item in json.loads(row[0])
            )
            if row
            else ()
        )

    def publish_diagnostics(
        self,
        user_id: str,
        generation: str,
        values: tuple[VehicleCoverageDiagnostic, ...],
    ) -> None:
        """Bind coverage to the same fenced offer publication."""
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO market_coverage SELECT user_id, generation, ? "
                "FROM market_preparations WHERE user_id=? AND generation=? "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "generation=excluded.generation, payload=excluded.payload",
                (json.dumps([asdict(v) for v in values]), user_id, generation),
            )

    def request(self, user_id: str, generation: str, now: float) -> None:
        """Enqueue changed demand without resetting unchanged retry timing."""
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO market_preparations VALUES (?, ?, ?, 'partial',"
                "NULL, ?) ON CONFLICT(user_id) DO UPDATE SET "
                "generation=excluded.generation, status='partial', "
                "next_retry_at=NULL, updated_at=excluded.updated_at "
                "WHERE market_preparations.generation<>excluded.generation",
                (user_id, uuid.uuid4().hex, generation, now),
            )

    def status(self, user_id: str) -> PreparationStatus | None:
        """Read the bound player's public preparation projection."""
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT preparation_id, generation, status, next_retry_at "
                "FROM market_preparations WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return PreparationStatus(*row) if row else None

    def next_player(self, now: float) -> str | None:
        """Choose the oldest due batch so active players share the worker."""
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT user_id FROM market_preparations "
                "WHERE (status='partial' AND next_retry_at IS NULL) "
                "OR next_retry_at<=? "
                "ORDER BY updated_at, user_id LIMIT 1",
                (now,),
            ).fetchone()
        return row[0] if row else None

    def finish(
        self,
        user_id: str,
        generation: str,
        status: str,
        retry_at: float | None,
        now: float,
    ) -> None:
        """Update only the demand generation actually processed."""
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE market_preparations SET status=?, next_retry_at=?, "
                "updated_at=? WHERE user_id=? AND generation=?",
                (status, retry_at, now, user_id, generation),
            )
