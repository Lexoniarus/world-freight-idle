"""Append-only provider attempt evidence."""

from dataclasses import asdict

from app.domain.routing_readiness import RoutingAttempt
from app.repositories.game_database import SqliteGameDatabase


class SqliteRoutingAttemptRepository:
    """Append routing diagnostics without replacing previous attempts."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Bind attempt writes to the shared game database."""
        self.database = database

    def append(self, attempt: RoutingAttempt) -> None:
        """Append evidence; previous failures are never overwritten."""
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO routing_attempts "
                "(subject_id, method, outcome, observed_at, trace_id, "
                "candidate_lat, candidate_lon, provider_code, "
                "provider_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(asdict(attempt).values()),
            )
