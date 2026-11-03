"""Lease fencing for shared routing preparation work."""

from app.repositories.game_database import SqliteGameDatabase


class SqliteRoutingLeaseRepository:
    """Acquire, renew and release global routing leases."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Bind lease operations to the shared game database."""
        self.database = database

    def acquire(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool:
        """Acquire only an absent or expired globally shared lease."""
        if expires_at <= now:
            raise ValueError("Lease must expire in the future.")
        with self.database.connect() as connection:
            result = connection.execute(
                "INSERT INTO routing_leases VALUES (?, ?, ?) "
                "ON CONFLICT(subject) DO UPDATE SET owner=excluded.owner, "
                "expires_at=excluded.expires_at "
                "WHERE routing_leases.expires_at<=?",
                (subject, owner, expires_at, now),
            )
            return result.rowcount == 1

    def renew(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool:
        """Extend a still-owned lease without resurrecting expired work."""
        if expires_at <= now:
            raise ValueError("Lease must expire in the future.")
        with self.database.connect() as connection:
            result = connection.execute(
                "UPDATE routing_leases SET expires_at=? "
                "WHERE subject=? AND owner=? AND expires_at>?",
                (expires_at, subject, owner, now),
            )
            return result.rowcount == 1

    def release(self, subject: str, owner: str) -> None:
        """Release only this owner's lease, including cancellation cleanup."""
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM routing_leases WHERE subject=? AND owner=?",
                (subject, owner),
            )

    def holds(self, subject: str, owner: str, now: float) -> bool:
        """Check ownership in the caller's publication transaction."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM routing_leases WHERE subject=? "
                "AND owner=? AND expires_at>?",
                (subject, owner, now),
            ).fetchone()
        return row is not None
