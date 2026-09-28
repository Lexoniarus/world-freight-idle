"""Account auxiliary storage, independent of the relational game schema."""

from contextlib import AbstractContextManager

from app.repositories.game_database import SqliteGameDatabase


class SqlitePreferenceStore:
    """Own a small account table without rewriting any game snapshots."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Bind storage and initialize its separate account table."""
        self.database = database
        with database.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS account_preferences (
                user_id TEXT PRIMARY KEY
                    REFERENCES users(id) ON DELETE CASCADE,
                company_color TEXT NOT NULL
            )""")

    def transaction(self) -> AbstractContextManager[None]:
        """Expose the shared transaction to the preference service."""
        return self.database.transaction()

    def color(self, user_id: str) -> str | None:
        """Read a persisted choice without assigning a fallback."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT company_color FROM account_preferences "
                "WHERE user_id=?",
                (user_id,),
            ).fetchone()
            return row[0] if row is not None else None

    def save_color(self, user_id: str, color: str) -> None:
        """Store one preference within the service-owned transaction."""
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO account_preferences VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE
                SET company_color=excluded.company_color""",
                (user_id, color),
            )
