"""Relational public progress projection without account secrets."""

from app.domain.read_ports import RankingEntry
from app.repositories.game_database import SqliteGameDatabase


class SqliteLeaderboardReader:
    """Read counters plus offline arrivals without mutating player state."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        self._database = database

    def list_ranking(self, active_at: float) -> tuple[RankingEntry, ...]:
        """Count due active rows once; settled rows are already in counters."""
        with self._database.connect() as connection:
            rows = connection.execute(
                """SELECT u.username, COALESCE(p.completed, 0) +
                    (SELECT count(*) FROM transports t
                     WHERE t.user_id=u.id AND t.status='active'
                     AND t.arrives_at <= ?) AS completed
                    FROM users u LEFT JOIN player_states p ON p.user_id=u.id
                    ORDER BY completed DESC, u.created_at ASC, u.id ASC
                    LIMIT 100""",
                (active_at,),
            ).fetchall()
        return tuple(
            RankingEntry(username=row["username"], completed=row["completed"])
            for row in rows
        )
