"""Global SQLite unit of work for startup market replacement."""

from contextlib import AbstractContextManager
from dataclasses import dataclass

from app.repositories.game_database import SqliteGameDatabase


@dataclass(slots=True)
class SqliteMarketStartupStore:
    """Share one outer database transaction across player repositories."""

    database: SqliteGameDatabase

    def transaction(self) -> AbstractContextManager[None]:
        """Expose transaction ownership without leaking a connection."""
        return self.database.transaction()

    def player_ids(self) -> tuple[str, ...]:
        """Read only initialized profiles, in stable owner order."""
        with self.database.connect() as connection:
            return tuple(
                row[0]
                for row in connection.execute(
                    "SELECT user_id FROM player_states ORDER BY user_id"
                )
            )
